import argparse
from pathlib import Path
from typing import Optional, Sequence

from utils import RESOURCE_TYPES, get_resources, install_resources


def pack_directory(value: str) -> Path:
    """Validate a command-line pack directory."""
    path = Path(value)
    if not path.is_dir() or not (path / "pack.toml").is_file():
        raise argparse.ArgumentTypeError(f"not a packwiz project directory: {value}")
    return path


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    """Parse sync arguments and provide standard argparse help."""
    parser = argparse.ArgumentParser(
        description=(
            "Install resources missing from TARGET by using metadata names from SOURCE. "
            "Installs are sequential because packwiz rewrites shared project files."
        )
    )
    parser.add_argument("source", type=pack_directory, help="source packwiz directory")
    parser.add_argument("target", type=pack_directory, help="target packwiz directory")
    return parser.parse_args(argv)


def sync_resources(source: Path, target: Path, resource_type: str) -> list[str]:
    """Install resources of one type that are absent from the target pack."""
    return install_resources(
        target,
        get_resources(source, resource_type),
        resource_type=resource_type,
    )


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    failures = {}
    for resource_type in RESOURCE_TYPES:
        failed = sync_resources(args.source, args.target, resource_type)
        if failed:
            failures[resource_type] = failed

    for resource_type, resources in failures.items():
        print(f"Failed to sync {resource_type}:")
        for resource in resources:
            print(f"  - {resource}")

    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
