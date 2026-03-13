# LunarFox

LunarFox is a utility-oriented modpack for Minecraft Java Edition, primarily providing performance optimizations, shader support, and a suite of survival assistance tools.

**Important Notes:**

- This modpack is **not** designed for ultimate performance. While it typically offers considerable FPS improvements, it does not promise to achieve theoretical best performance.
- This modpack **does not modify vanilla game mechanics**, allowing you to join any **vanilla server** without issues. However, please note: during multiplayer, if the host uses this modpack while guests use different versions, connection issues may occur due to missing mods or version mismatches. It is strongly recommended that all participants use the exact same version.
- To reduce cognitive load from new features, **some features are hidden or disabled by default**. You may manually enable them as needed.
- Currently, the Fabric version is actively maintained. NeoForge/Forge versions receive limited support only for mainstream game versions.
- Given the complexity of the modding ecosystem, this modpack cannot cover all scenarios or exhaustive testing. If you encounter issues or have suggestions for improvement, please provide feedback through the following channels:
  - [MCMOD](https://www.mcmod.cn/modpack/1089.html)
  - [Codeberg Issues](https://codeberg.org/OrzMiku/lunarfox/issues)
  - QQ Group: 938526800

## Q&A

**1. How do I install the modpack?**

If your launcher supports search installation, you can directly search for "LunarFox" and install it with one click. For manual installation, please download the corresponding modpack file from [Modrinth](https://modrinth.com/modpack/lunarfox) and complete the installation via your launcher's "Import" function.

**2. Is there a server-side version?**

No. LunarFox is a client-side only modpack compatible with vanilla servers; no dedicated server-side deployment is required.

**3. What is the info display in the top-left corner? How do I adjust it?**

This is the [MiniHUD](https://modrinth.com/mod/minihud) mod. Press `H` in-game to quickly toggle the display, and press `H+C` to open the configuration interface for customization.

**4. Is there a vein mining feature?**

Not currently included. Adhering to the design philosophy of preserving vanilla mechanics, the modpack does not pre-install vein mining mods. If you need this feature, we recommend adding one of the following:

- [FTB Ultimine (Fabric)](https://www.curseforge.com/minecraft/mc-mods/ftb-ultimine-fabric)
- [FTB Ultimine (Forge)](https://www.curseforge.com/minecraft/mc-mods/ftb-ultimine-forge)
- [Veinminer](https://modrinth.com/datapack/veinminer)

**5. Can I play multiplayer?**

Yes. However, it is strongly recommended that all players use the exact same version of the modpack to avoid potential issues.

## Dev

This modpack is managed using [packwiz](https://packwiz.infra.link/) combined with Python scripts for automation:

- `${repo_root}/versions/<mod_loader>/<game_version>`: Independent packwiz project directories managing mod configurations for corresponding versions.
- `${repo_root}/archived/<mod_loader>/<game_version>`: Archived historical versions that have ceased maintenance.
- `${repo_root}/scripts`: Maintenance tool scripts directory
  - `export.py`: Batch export release files for all versions.
  - `update.py`: Batch check and update mod versions.
  - `sync.py`: Cross-version mod synchronization tool, facilitating quick migration of configurations from one version to another.
