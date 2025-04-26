# 项目脚本说明

此目录包含用于管理和维护此 Minecraft 整合包项目的辅助脚本。

## 目录

- [export_packs.py](#export_packspy)
- [update_packs.py](#update_packspy)
- [version_migrator.py](#version_migratorpy)

---

## `export_packs.py`

### 功能目的

此脚本用于将 `versions` 目录下的每个 packwiz 整合包版本导出为 Modrinth 使用的 `.mrpack` 文件格式。它会自动清理旧的导出文件，并可以选择性地在导出的文件名中附加 Git commit hash。

### 用法

```bash
python scripts/export_packs.py [commit_hash] [options]
```

### 参数

| 参数             | 位置/可选 | 说明                                                                 | 默认值    |
| ---------------- | -------- | -------------------------------------------------------------------- | -------- |
| `commit_hash`    | 位置参数 (可选) | 要附加到 `.mrpack` 文件名末尾的短 Git commit hash。如果省略，则不重命名。 | `None`   |
| `--versions-dir` | 可选     | 包含各个版本子目录（每个子目录是一个 packwiz 项目）的根目录。         | `versions` |
| `--packwiz-cmd`  | 可选     | `packwiz` 可执行文件的路径或命令名。                                   | `packwiz`  |
| `--log-dir`      | 可选     | 用于存储日志文件的目录。                                               | `logs`     |
| `--timeout`      | 可选     | `packwiz mr export` 命令的超时时间（秒）。                             | `120`      |
| `-v`, `--verbose`| 可选标志 | 启用详细的调试级别日志输出到控制台。                                   | `False`    |

### 前置条件/依赖项

- 需要安装 `packwiz` 可执行文件，并且能在系统的 PATH 中找到，或者通过 `--packwiz-cmd` 指定其路径。

### 典型使用场景示例

1. **导出所有版本，不附加 commit hash**:

    ```bash
    python scripts/export_packs.py
    ```

2. **导出所有版本，并将短 commit hash `a1b2c3d` 附加到文件名**:

    ```bash
    python scripts/export_packs.py a1b2c3d
    ```

3. **指定 `packwiz` 路径并启用详细日志**:

    ```bash
    python scripts/export_packs.py --packwiz-cmd /path/to/packwiz --verbose
    ```

---

## `update_packs.py`

### 功能目的 (update_packs.py)

此脚本用于更新 `versions` 目录下所有 packwiz 整合包版本中的模组和配置。它会为每个版本目录执行 `packwiz update --all` 命令，并自动确认更新提示。

### 用法 (update_packs.py)

```bash
python scripts/update_packs.py [options]
```

### 参数 (update_packs.py)

| 参数             | 可选     | 说明                                                                 | 默认值    |
| ---------------- | -------- | -------------------------------------------------------------------- | -------- |
| `--versions-dir` | 可选     | 包含各个版本子目录（每个子目录是一个 packwiz 项目）的根目录。         | `versions` |
| `--packwiz-cmd`  | 可选     | `packwiz` 可执行文件的路径或命令名。                                   | `packwiz`  |
| `--log-dir`      | 可选     | 用于存储日志文件的目录。                                               | `logs`     |
| `--timeout`      | 可选     | `packwiz update --all` 命令的超时时间（秒）。                          | `300`      |
| `-v`, `--verbose`| 可选标志 | 启用详细的调试级别日志输出到控制台。                                   | `False`    |

### 前置条件/依赖项 (update_packs.py)

- 需要安装 `packwiz` 可执行文件，并且能在系统的 PATH 中找到，或者通过 `--packwiz-cmd` 指定其路径。

### 典型使用场景示例 (update_packs.py)

1. **更新所有版本**:

    ```bash
    python scripts/update_packs.py
    ```

2. **指定 `packwiz` 路径并增加超时时间**:

    ```bash
    python scripts/update_packs.py --packwiz-cmd /usr/local/bin/packwiz --timeout 600
    ```

---

## `version_migrator.py`

### 功能目的 (version_migrator.py)

此脚本用于将一个源目录结构（包含新的模组和资源包文件）中的内容迁移（添加）到一个目标 packwiz 整合包实例中。它会扫描源目录，识别出目标 packwiz 实例中尚不存在的项目，然后使用 `packwiz mr add <slug_or_id>` 命令将这些新项目添加到目标实例。

**关键假设**: 脚本假定源目录中的文件名（去除 `.jar` 或 `.pw.toml` 后缀）直接对应于 Modrinth 或 CurseForge 上的项目 slug 或 ID。

### 用法 (version_migrator.py)

```bash
python scripts/version_migrator.py <source_root> <packwiz_dir> [options]
```

### 参数 (version_migrator.py)

| 参数                      | 位置/可选 | 说明                                                                                                                               | 默认值        |
| ------------------------- | -------- | ---------------------------------------------------------------------------------------------------------------------------------- | ------------ |
| `source_root`             | 位置参数 (必需) | 包含待扫描子目录（例如 `mods/`, `resourcepacks/`）的源根目录。                                                                       | N/A          |
| `packwiz_dir`             | 位置参数 (必需) | 目标 packwiz 项目的根目录（即包含 `pack.toml` 文件的目录）。                                                                       | N/A          |
| `--mods-src-dir`          | 可选     | 在 `source_root` 下，包含待扫描模组文件的子目录名称。                                                                                | `mods`         |
| `--resourcepacks-src-dir` | 可选     | 在 `source_root` 下，包含待扫描资源包文件的子目录名称。                                                                              | `resourcepacks`|
| `--packwiz-cmd`           | 可选     | `packwiz` 可执行文件的路径或命令名。                                                                                                 | `packwiz`      |
| `--log-dir`               | 可选     | 用于存储日志文件的目录。                                                                                                             | `logs`         |
| `--timeout`               | 可选     | 每个 `packwiz mr add` 命令的超时时间（秒）。                                                                                         | `60`           |
| `--retries`               | 可选     | 如果 `packwiz mr add` 命令因超时失败，允许的最大重试次数。                                                                             | `3`            |
| `-y`, `--yes`             | 可选标志 | 自动对“是否继续添加”的确认提示回答“是”，跳过手动确认步骤。                                                                           | `False`        |
| `-v`, `--verbose`         | 可选标志 | 启用详细的调试级别日志输出到控制台。                                                                                                 | `False`        |

### 前置条件/依赖项 (version_migrator.py)

- 需要安装 `packwiz` 可执行文件，并且能在系统的 PATH 中找到，或者通过 `--packwiz-cmd` 指定其路径。
- **重要**: 源目录（例如 `source_root/mods/`）中的文件名（去除 `.jar` 或 `.pw.toml` 后缀后）**必须**是 `packwiz mr add` 命令可以识别的有效 Modrinth 或 CurseForge 项目 slug 或 ID。例如，如果想添加 Fabric API，源目录中应包含名为 `fabric-api.jar` 或 `fabric-api.pw.toml` 的文件。
- （可选）如果你的 Python 版本低于 3.11，并且你想让脚本从目标 `pack.toml` 文件中动态读取 `mods-folder` 和 `resourcepacks-folder` 的设置（而不是使用默认的 `mods` 和 `resourcepacks`），你需要安装 `tomli` 库 (`pip install tomli`)。

### 典型使用场景示例 (version_migrator.py)

假设你有一个临时目录 `/tmp/new_stuff`，结构如下：

```text
/tmp/new_stuff/
├── mods/
│   ├── sodium.jar          # 文件名是 slug
│   └── iris.pw.toml        # 文件名是 slug
└── resourcepacks/
    └── faithful-32x.pw.toml # 文件名是 slug
```

而你的 packwiz 项目位于 `./versions/1.21.5`。

1. **扫描 `/tmp/new_stuff` 并将新内容添加到 `./versions/1.21.5`，需要手动确认**:

    ```bash
    python scripts/version_migrator.py /tmp/new_stuff ./versions/1.21.5
    ```

    脚本会列出找到的 `sodium`, `iris`, `faithful-32x`，并询问是否继续。

2. **扫描 `/tmp/new_stuff` 并自动添加，跳过确认**:

    ```bash
    python scripts/version_migrator.py /tmp/new_stuff ./versions/1.21.5 --yes
    ```

3. **如果源目录中的模组子目录名为 `mod_files` 而不是 `mods`**:

    ```bash
    python scripts/version_migrator.py /tmp/new_stuff ./versions/1.21.5 --mods-src-dir mod_files
    ```
