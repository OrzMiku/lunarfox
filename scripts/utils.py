import os
import subprocess
import tempfile
import tomllib
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Union

DEFAULT_VERSIONS_DIR = "versions"
PROGRESS_BAR_LENGTH = 20
RESOURCE_TYPES = ("mods", "resourcepacks", "shaderpacks")
PLATFORM_MODRINTH = "modrinth"

PathLike = Union[str, os.PathLike]


def get_all_versions(base_dir: Optional[PathLike] = None) -> Dict[str, List[str]]:
    """Return active pack directories grouped by mod loader."""
    root = Path(base_dir or Path.cwd() / DEFAULT_VERSIONS_DIR)
    if not root.is_dir():
        return {}

    return {
        loader.name: [str(version) for version in sorted(loader.iterdir()) if version.is_dir()]
        for loader in sorted(root.iterdir())
        if loader.is_dir()
        and any(version.is_dir() for version in loader.iterdir())
    }


def run_packwiz(
    directory: PathLike,
    args: Sequence[str],
    *,
    timeout: Optional[int] = None,
) -> None:
    """Run packwiz safely in one pack directory and propagate failures."""
    subprocess.run(
        ["packwiz", *args],
        cwd=directory,
        check=True,
        timeout=timeout,
    )


def export_modpacks(paths: Sequence[PathLike]) -> None:
    """Export packs to temporary files, then atomically replace final artifacts."""
    for path in paths:
        target = Path(path).resolve()
        pack = tomllib.loads((target / "pack.toml").read_text())
        filename = f"{pack['name']}-{pack['version']}.mrpack"
        if Path(filename).name != filename:
            raise ValueError(f"unsafe export filename: {filename}")

        descriptor, temporary_name = tempfile.mkstemp(
            dir=target,
            prefix=".packwiz-export-",
            suffix=".mrpack",
        )
        os.close(descriptor)
        temporary = Path(temporary_name)
        temporary.unlink()
        try:
            run_packwiz(
                target,
                [PLATFORM_MODRINTH, "export", "--output", str(temporary)],
            )
            destination = target / filename
            os.replace(temporary, destination)
            prefix = f"{pack['name']}-"
            for artifact in target.glob("*.mrpack"):
                if artifact != destination and artifact.name.startswith(prefix):
                    artifact.unlink()
        finally:
            temporary.unlink(missing_ok=True)


def update_modpacks(paths: Sequence[PathLike]) -> None:
    """Update packs sequentially because each command rewrites pack metadata."""
    total = len(paths)
    print(f"Starting updates for {total} modpacks...\n")

    for index, path in enumerate(paths, 1):
        print(f"{progress_bar(index - 1, total)} | Updating: {path}")
        print("=" * 60)
        run_packwiz(path, ["update", "--all", "--yes"])
        print(f"{progress_bar(index, total)} | {path} ✅ Completed\n")


def get_spec_from_filename(filename: str) -> str:
    """Return the packwiz project spec encoded by a metadata filename."""
    suffix = ".pw.toml"
    return filename[: -len(suffix)] if filename.endswith(suffix) else Path(filename).stem


def get_resources(
    version_path: PathLike,
    resource_type: str = "mods",
) -> List[str]:
    """Return resource files from one pack in deterministic order."""
    resources_dir = Path(version_path) / resource_type
    if not resources_dir.is_dir():
        return []

    return sorted(
        path.name
        for path in resources_dir.iterdir()
        if path.is_file() and path.name.endswith((".jar", ".pw.toml", ".zip"))
    )


def progress_bar(
    completed: int,
    total: int,
    length: int = PROGRESS_BAR_LENGTH,
) -> str:
    """Return a bounded textual progress bar."""
    if total <= 0:
        return f"[{'░' * length}] 0/0 (0.0%)"

    completed = min(max(completed, 0), total)
    filled_length = length * completed // total
    bar = "█" * filled_length + "░" * (length - filled_length)
    return f"[{bar}] {completed}/{total} ({completed / total * 100:.1f}%)"


def install_resources(
    version_path: PathLike,
    resource_list: Sequence[str],
    resource_type: str = "mods",
    platform: str = PLATFORM_MODRINTH,
) -> List[str]:
    """Install missing metadata sequentially into one packwiz project."""
    target = Path(version_path)
    if not target.is_dir():
        raise NotADirectoryError(target)

    installed = set(get_resources(target, resource_type))
    pending = list(dict.fromkeys(resource for resource in resource_list if resource not in installed))
    failures: List[str] = []

    for completed, resource in enumerate(pending, 1):
        error = None
        if not resource.endswith(".pw.toml"):
            error = "only .pw.toml resources can be installed by project name"
        else:
            try:
                run_packwiz(
                    target,
                    ["--yes", platform, "install", get_spec_from_filename(resource)],
                    timeout=300,
                )
            except (OSError, subprocess.SubprocessError) as exc:
                error = str(exc)

        status = "✅ Done" if error is None else f"❌ Failed: {error}"
        print(f"{progress_bar(completed, len(pending))} | {resource} {status}")
        if error is not None:
            failures.append(resource)

    return failures
