from utils import get_resources, install_resources
import argparse
import os


def parse_arguments():
    """
    解析命令行参数，确保提供的路径是目录。

    Returns:
        argparse.Namespace: 包含解析后参数的命名空间对象

    Raises:
        NotADirectoryError: 如果提供的路径不是目录
    """
    parser = argparse.ArgumentParser(description="Sync versions.")
    parser.add_argument(
        "version_1",
        type=str,
        help="Path to the first version directory, read as source version",
    )
    parser.add_argument(
        "version_2",
        type=str,
        help="Path to the second version directory, read as target version",
    )
    parser.add_argument(
        "currency",
        type=int,
        help="Number of concurrent downloads",
        default=4,
        nargs="?",
    )
    args = parser.parse_args()
    if os.path.isdir(args.version_1) and os.path.isdir(args.version_2):
        return args
    else:
        raise NotADirectoryError("One of the provided paths is not a directory.")


def sync_mods(source_version, target_version, currency=4):
    mods = get_resources(source_version, resource_type="mods")
    failed_mods = install_resources(
        target_version,
        mods,
        platform="modrinth",
        currency=currency,
        resource_type="mods",
    )
    return failed_mods


def sync_resourcepacks(source_version, target_version, currency=4):
    resourcepacks = get_resources(source_version, resource_type="resourcepacks")
    failed_resourcepacks = install_resources(
        target_version,
        resourcepacks,
        platform="modrinth",
        currency=currency,
        resource_type="resourcepacks",
    )
    return failed_resourcepacks


def sync_shaders(source_version, target_version, currency=4):
    shaders = get_resources(source_version, resource_type="shaderpacks")
    failed_shaders = install_resources(
        target_version,
        shaders,
        platform="modrinth",
        currency=currency,
        resource_type="shaderpacks",
    )
    return failed_shaders


def main():
    args = parse_arguments()
    source_versions = args.version_1
    target_versions = args.version_2
    currency = args.currency

    failed_mods = sync_mods(source_versions, target_versions, currency)
    failed_resourcepacks = sync_resourcepacks(
        source_versions, target_versions, currency
    )
    failed_shaders = sync_shaders(source_versions, target_versions, currency)

    if failed_mods:
        print("Failed to sync the following mods:")
        for mod in failed_mods:
            print(f"  - {mod}")

    if failed_resourcepacks:
        print("Failed to sync the following resource packs:")
        for rp in failed_resourcepacks:
            print(f"  - {rp}")

    if failed_shaders:
        print("Failed to sync the following shaders:")
        for shader in failed_shaders:
            print(f"  - {shader}")


if __name__ == "__main__":
    main()
