from utils import get_resources, install_resources
import argparse
import os
from typing import List


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
        "concurrency",
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


def sync_resources(
    source_version: str,
    target_version: str,
    resource_type: str,
    concurrency: int = 4,
) -> List[str]:
    """
    同步资源（模组/资源包/着色器）从源版本到目标版本。

    Args:
        source_version (str): 源版本目录路径
        target_version (str): 目标版本目录路径
        resource_type (str): 资源类型 ('mods', 'resourcepacks', 'shaderpacks')
        concurrency (int): 并发数，默认 4

    Returns:
        list: 同步失败的资源列表
    """
    resources = get_resources(source_version, resource_type=resource_type)
    failed_resources = install_resources(
        target_version,
        resources,
        platform="modrinth",
        concurrency=concurrency,
        resource_type=resource_type,
    )
    return failed_resources


def main():
    args = parse_arguments()
    source_versions = args.version_1
    target_versions = args.version_2
    concurrency = args.concurrency

    # 同步所有类型的资源
    resource_types = {
        "mods": "mods",
        "resource packs": "resourcepacks",
        "shaders": "shaderpacks",
    }

    failed_by_type = {}
    for display_name, resource_type in resource_types.items():
        failed = sync_resources(
            source_versions, target_versions, resource_type, concurrency
        )
        if failed:
            failed_by_type[display_name] = failed

    # 输出失败的资源
    for display_name, failed_list in failed_by_type.items():
        print(f"Failed to sync the following {display_name}:")
        for resource in failed_list:
            print(f"  - {resource}")


if __name__ == "__main__":
    main()
