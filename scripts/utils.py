import os
import concurrent.futures
import subprocess
from typing import Dict, List, Optional

# Constants
DEFAULT_VERSIONS_DIR = "versions"
DEFAULT_CONCURRENCY = 4
PROGRESS_BAR_LENGTH = 20

# Resource types
RESOURCE_TYPE_MODS = "mods"
RESOURCE_TYPE_RESOURCEPACKS = "resourcepacks"
RESOURCE_TYPE_SHADERPACKS = "shaderpacks"

# Supported platforms
PLATFORM_MODRINTH = "modrinth"
PLATFORM_CURSEFORGE = "curseforge"

# Format extensions
FORMAT_EXTENSIONS = {
    PLATFORM_MODRINTH: "mrpack",
    PLATFORM_CURSEFORGE: "zip",
}


def get_all_versions(base_dir: Optional[str] = None) -> Dict[str, List[str]]:
    """
    扫描并返回所有模组加载器及其版本目录。

    Args:
        base_dir (str, optional): 基础目录路径，默认为 './versions'

    Returns:
        dict: {mod_loader: [version_path, ...]} 格式的字典
    """
    if base_dir is None:
        base_dir = os.path.join(os.getcwd(), DEFAULT_VERSIONS_DIR)
    result = {}

    if not os.path.isdir(base_dir):
        return result

    for mod_loader in os.listdir(base_dir):
        mod_loader_path = os.path.join(base_dir, mod_loader)
        if not os.path.isdir(mod_loader_path):
            continue

        versions = []
        for version in os.listdir(mod_loader_path):
            version_path = os.path.join(mod_loader_path, version)
            if os.path.isdir(version_path):
                versions.append(version)

        if versions:
            result[mod_loader] = [os.path.join(mod_loader_path, v) for v in versions]

    return result


def run_command_in_dir(command: str, directory: str) -> None:
    """
    在指定目录中执行命令。

    Args:
        command (str): 要执行的命令
        directory (str): 目标目录路径
    """
    original_dir = os.getcwd()
    try:
        os.chdir(directory)
        subprocess.run(command, shell=True, check=False)
    finally:
        os.chdir(original_dir)


def cleanup_old_packs(path: str, format: str) -> None:
    """
    清理指定目录下的旧模组包文件。

    Args:
        path (str): 目标目录路径
        format (str): 模组包格式 ('modrinth' 或 'curseforge')
    """
    ext = FORMAT_EXTENSIONS.get(format)
    if ext is None:
        return

    for file in os.listdir(path):
        if file.endswith(f".{ext}"):
            os.remove(os.path.join(path, file))


def export_modpacks(paths: List[str], format: str = PLATFORM_MODRINTH, cleanup: bool = True) -> None:
    """
    批量导出模组包文件。

    Args:
        paths (list): 目标路径列表
        format (str): 导出格式，默认 'modrinth'
        cleanup (bool): 是否在导出前清理旧文件，默认 True
    """
    if cleanup:
        for path in paths:
            cleanup_old_packs(path, format)
    for path in paths:
        run_command_in_dir(f"packwiz {format} export", path)


def update_modpacks(paths: List[str], concurrency: int = DEFAULT_CONCURRENCY) -> None:
    """
    批量更新模组包文件。

    注意：由于 os.chdir() 在多线程环境下不安全（会影响整个进程的工作目录），
    此函数使用顺序执行而非并发执行。

    Args:
        paths (list): 目标路径列表
        concurrency (int): 保留参数以兼容旧版本，但不再使用
    """
    total = len(paths)
    print(f"Starting updates for {total} modpacks...\n")

    for idx, path in enumerate(paths, 1):
        print(f"{progress_bar(idx - 1, total)} | Updating: {path}")
        print(f"{'='*60}")

        original_dir = os.getcwd()
        try:
            os.chdir(path)
            subprocess.run("packwiz update --all --yes", shell=True, text=True)
        finally:
            os.chdir(original_dir)

        print(f"{progress_bar(idx, total)} | {path} ✅ Completed\n")


def get_spec_from_filename(filename: str) -> str:
    """
    从文件名中提取模组规格（不含扩展名）。

    Args:
        filename (str): 文件名

    Returns:
        str: 模组规格
    """
    if filename.endswith(".pw.toml"):
        return filename[: -len(".pw.toml")]
    else:
        return os.path.splitext(filename)[0]


def get_resources(version_path: str, resource_type: str = RESOURCE_TYPE_MODS) -> List[str]:
    """
    获取指定目录下的所有模组/资源包/着色器文件。

    Args:
        version_path (str): 目标目录路径
        resource_type (str): 资源类型，默认 'mods'

    Returns:
        list: 资源文件列表
    """
    resources_dir = os.path.join(version_path, resource_type)
    if not os.path.isdir(resources_dir):
        return []

    return [
        f
        for f in os.listdir(resources_dir)
        if os.path.isfile(os.path.join(resources_dir, f))
        and (f.endswith(".jar") or f.endswith(".pw.toml") or f.endswith(".zip"))
    ]


def progress_bar(completed: int, total: int, length: int = PROGRESS_BAR_LENGTH) -> str:
    """
    生成进度条字符串。

    Args:
        completed (int): 已完成的任务数
        total (int): 总任务数
        length (int): 进度条长度，默认 20

    Returns:
        str: 进度条字符串
    """
    filled_length = int(length * completed // total)
    bar = "█" * filled_length + "░" * (length - filled_length)
    percent = completed / total * 100
    return f"[{bar}] {completed}/{total} ({percent:.1f}%)"


def install_resources(
    version_path: str,
    resource_list: List[str],
    resource_type: str = RESOURCE_TYPE_MODS,
    platform: str = PLATFORM_MODRINTH,
    concurrency: int = DEFAULT_CONCURRENCY,
) -> List[str]:
    """
    安装指定列表中的资源到目标版本目录。

    Args:
        version_path (str): 目标版本目录路径
        resource_list (list): 要安装的模组/资源包/着色器文件列表
        resource_type (str): 资源类型，'mods', 'resourcepacks', 'shaderpacks'
        platform (str): 平台，默认 'modrinth', 可选 'curseforge'
        concurrency (int): 并发数，默认 4

    Returns:
        list: 安装失败的资源文件列表
    """
    if not os.path.isdir(version_path):
        return []

    # 去重
    already_resources = get_resources(version_path, resource_type)
    resource_list = [m for m in resource_list if m not in already_resources]
    if not resource_list:
        return []

    original_dir = os.getcwd()
    os.chdir(version_path)

    def install_single_resource(resource: str) -> Optional[str]:
        """安装单个资源并返回结果"""
        try:
            if not resource.endswith(".pw.toml"):
                return resource
            command = f"packwiz -y {platform} install {get_spec_from_filename(resource)}"
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=300,  # 5分钟超时
            )
            if result.returncode != 0:
                return resource  # 返回失败的资源
            return None  # 成功则返回 None
        except (subprocess.TimeoutExpired, Exception):
            return resource  # 异常或超时也视为失败

    failed_resources = []
    try:
        total = len(resource_list)
        have_done = 0
        max_workers = min(concurrency, len(resource_list))
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            # 提交所有任务
            future_to_resource = {
                executor.submit(install_single_resource, resource): resource
                for resource in resource_list
            }

            # 收集结果
            for future in concurrent.futures.as_completed(future_to_resource):
                have_done += 1
                result = future.result()
                print(
                    f"{progress_bar(have_done, total)} | {future_to_resource[future]} {'✅ Done' if result is None else '❌ Failed'}"
                )
                if result is not None:  # 如果返回了资源名，说明失败了
                    failed_resources.append(result)

    finally:
        os.chdir(original_dir)

    return failed_resources
