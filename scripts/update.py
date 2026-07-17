import argparse
from typing import Optional, Sequence

from utils import get_all_versions, update_modpacks


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    """Parse command-line arguments; argparse also owns --help output."""
    parser = argparse.ArgumentParser(
        description="Update every external resource in every active LunarFox pack."
    )
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    parse_args(argv)
    for paths in get_all_versions().values():
        update_modpacks(paths)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
