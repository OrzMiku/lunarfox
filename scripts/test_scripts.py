import contextlib
import io
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import call, patch

import export
import sync
import update
import utils


class PackwizHelpersTest(unittest.TestCase):
    def test_run_packwiz_uses_argv_and_cwd(self) -> None:
        with patch.object(utils.subprocess, "run") as run:
            utils.run_packwiz("pack", ["modrinth", "install", "a;echo unsafe"])

        run.assert_called_once_with(
            ["packwiz", "modrinth", "install", "a;echo unsafe"],
            cwd="pack",
            check=True,
            timeout=None,
        )

    def test_export_failure_preserves_existing_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            pack = Path(directory)
            (pack / "pack.toml").write_text('name = "LunarFox"\nversion = "1.0"\n')
            artifact = pack / "LunarFox-1.0.mrpack"
            artifact.write_text("existing")
            error = subprocess.CalledProcessError(1, ["packwiz"])

            with patch.object(utils, "run_packwiz", side_effect=error):
                with self.assertRaises(subprocess.CalledProcessError):
                    utils.export_modpacks([pack])

            self.assertEqual(artifact.read_text(), "existing")
            self.assertEqual(list(pack.glob(".packwiz-export-*")), [])

    def test_successful_export_atomically_replaces_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            pack = Path(directory)
            (pack / "pack.toml").write_text('name = "LunarFox"\nversion = "1.0"\n')
            artifact = pack / "LunarFox-1.0.mrpack"
            artifact.write_text("existing")
            obsolete = pack / "LunarFox-0.9.mrpack"
            obsolete.write_text("old")
            unrelated = pack / "Other-0.9.mrpack"
            unrelated.write_text("keep")

            def create_export(_directory, args, **_kwargs) -> None:
                Path(args[-1]).write_text("new")

            with patch.object(utils, "run_packwiz", side_effect=create_export):
                utils.export_modpacks([pack])

            self.assertEqual(artifact.read_text(), "new")
            self.assertFalse(obsolete.exists())
            self.assertTrue(unrelated.exists())
            self.assertEqual(list(pack.glob(".packwiz-export-*")), [])

    def test_update_failure_is_not_reported_as_completed(self) -> None:
        output = io.StringIO()
        error = subprocess.CalledProcessError(1, ["packwiz"])

        with patch.object(utils, "run_packwiz", side_effect=error):
            with contextlib.redirect_stdout(output):
                with self.assertRaises(subprocess.CalledProcessError):
                    utils.update_modpacks(["pack"])

        self.assertNotIn("Completed", output.getvalue())

    def test_installs_are_sequential_and_failures_are_returned(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            error = subprocess.CalledProcessError(1, ["packwiz"])
            with patch.object(utils, "run_packwiz", side_effect=[None, error]) as run:
                failures = utils.install_resources(
                    directory,
                    ["first.pw.toml", "second;echo unsafe.pw.toml"],
                )

        self.assertEqual(failures, ["second;echo unsafe.pw.toml"])
        self.assertEqual(
            run.call_args_list,
            [
                call(
                    Path(directory),
                    ["--yes", "modrinth", "install", "first"],
                    timeout=300,
                ),
                call(
                    Path(directory),
                    ["--yes", "modrinth", "install", "second;echo unsafe"],
                    timeout=300,
                ),
            ],
        )


class ScriptCliTest(unittest.TestCase):
    def test_every_script_has_standard_help(self) -> None:
        for parse_args in (export.parse_args, update.parse_args, sync.parse_args):
            with self.subTest(module=parse_args.__module__):
                with contextlib.redirect_stdout(io.StringIO()):
                    with self.assertRaises(SystemExit) as raised:
                        parse_args(["--help"])
                self.assertEqual(raised.exception.code, 0)

    def test_sync_returns_nonzero_when_any_resource_fails(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            source = Path(root) / "source"
            target = Path(root) / "target"
            for pack in (source, target):
                pack.mkdir()
                (pack / "pack.toml").touch()

            with patch.object(
                sync,
                "sync_resources",
                side_effect=[[], ["failed.pw.toml"], []],
            ):
                with contextlib.redirect_stdout(io.StringIO()):
                    result = sync.main([str(source), str(target)])

        self.assertEqual(result, 1)

    def test_sync_rejects_non_pack_directories(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as raised:
                    sync.parse_args([directory, directory])

        self.assertEqual(raised.exception.code, 2)


if __name__ == "__main__":
    unittest.main()
