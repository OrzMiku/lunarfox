# LunarFox

LunarFox 是一款面向 Minecraft Java 版的实用向整合包，主要提供性能优化、光影着色器支持及一系列生存辅助工具。

**重要说明：**

- 本整合包**并非**为极致性能而生。虽然通常能提供可观的帧率表现，但不承诺达到理论上的最佳性能。
- 本整合包**不会修改原版游戏机制**，因此你可以毫无障碍地加入任何**原版服务器**。但请注意：多人联机时，若房主使用本整合包而房客使用不同版本，可能因为模组缺失、模组版本不匹配导致无法联机。建议所有参与者统一使用相同版本。
- 为减少新功能带来的认知负担，**部分特性默认处于隐藏或禁用状态**，你可按需手动开启。
- 目前主要维护 Fabric 版本。NeoForge/Forge 版本仅针对主流游戏版本提供有限支持。
- 鉴于模组生态的复杂性，本整合包无法覆盖所有场景，亦无法穷尽测试。如遇问题或有改进建议，欢迎通过以下渠道反馈：
  - [MC百科](https://www.mcmod.cn/modpack/1089.html)
  - [Codeberg Issues](https://codeberg.org/OrzMiku/lunarfox/issues)
  - QQ 交流群：938526800

## Q&A

**1. 如何安装整合包？**

若你使用的启动器支持搜索安装，可直接搜索 "LunarFox" 一键安装。如需手动安装，请前往 [Modrinth](https://modrinth.com/modpack/lunarfox) 下载对应整合包文件，并通过启动器的"导入"功能完成安装。

**2. 有服务器端吗？**

没有。LunarFox 为纯客户端整合包，兼容原版服务端，无需部署专门的服务器端。

**3. 左上角的信息显示是什么？如何调整？**

这是 [MiniHUD](https://modrinth.com/mod/minihud) 模组。游戏中按 `H` 键可快速开关显示，按 `H+C` 打开配置界面进行自定义。

**4. 有连锁采集功能吗？**

目前未内置。出于遵循原版机制的设计理念，整合包未预装连锁采集类模组。如需此功能，推荐添加以下模组之一：

- [FTB Ultimine (Fabric)](https://www.curseforge.com/minecraft/mc-mods/ftb-ultimine-fabric)
- [FTB Ultimine (Forge)](https://www.curseforge.com/minecraft/mc-mods/ftb-ultimine-forge)
- [Veinminer](https://modrinth.com/datapack/veinminer)

**5. 可以联机游戏吗？**

可以。但强烈建议所有玩家使用完全相同的整合包版本，以避免出现问题。

## Dev

本整合包使用 [packwiz](https://packwiz.infra.link/) 结合 Python 脚本进行自动化管理：

- `${repo_root}/versions/<mod_loader>/<game_version>`：独立的 packwiz 项目目录，管理对应版本的模组配置。
- `${repo_root}/archived/<mod_loader>/<game_version>`：已停止维护的历史版本归档。
- `${repo_root}/scripts`：维护工具脚本目录
  - `export.py`：批量导出所有版本的发布文件。
  - `update.py`：批量检查并更新模组版本。
  - `sync.py`：跨版本模组同步工具，便于将一个版本的配置快速迁移至另一版本。
