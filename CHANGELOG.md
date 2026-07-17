# Changelog

All notable changes to this project will be documented in this file.

## [1.3.4-beta.2] - 2026-07-18

### Added

- Added initial Fabric 26.2 support as `0.1.0-alpha.2`, including the standard mod, resource pack, shader pack, and default configuration set.
- Added AsyncParticles, Carpet, CIT Resewn Continuation, Polytone, and YOSBR to Fabric 26.1.2, together with the required configuration library.
- Added automated tests for the modpack maintenance scripts.

### Changed

- Updated mods, resource packs, and shader packs across supported versions.
- Moved the Fabric 26.1.2 and 26.2 default configurations into YOSBR so they are applied only to new installations.
- Updated the Xaero map translation resource pack filename in the Fabric 1.21.1 defaults.
- Simplified the maintenance scripts with version filters, standard help output, validated sync targets, safe subprocess argument handling, and atomic exports.

### Removed

- Removed Iris Shader Folder and its configuration from all supported versions.

### Fixed

- Fixed failed exports deleting an existing modpack archive.
- Fixed update and resource sync failures being reported as successful.

## [1.3.4-beta.1] - 2026-06-14

### Added

- Added AsyncParticles, Better Ping Display, Krypton, Polytone, Stendhal, and Title Fixer (Fabric 1.21.11).
- Added Better Advancements, Chat Patches, Held Item Info, JustEnoughCharacters, Modern UI, OptiGUI, Pick Up Notifier, Status Effect Bars, and Structure Layout Optimizer (Fabric 26.1.2).
- Added default configs for Better Advancements and Chat Patches (Fabric 26.1.2).

### Changed

- Updated mod loaders to Fabric Loader 0.19.3 and NeoForge 21.1.233.
- Updated mods, resource packs, and shader packs across supported versions.

### Removed

- Removed bettergrassify mod (Fabric 1.21.1).

### Fixed

- Fixed the incompatibility issue between the chat head and modern UI, where the chat head fails to display (Fabric 1.21.1, Fabric 1.21.11, NeoForge 1.21.1).

## [1.3.3] - 2026-04-27

- Adjust shortcut key bindings.
- Fix the list of resource packs enabled by default.

## [1.3.2] - 2026-04-03

- Added the cubes without borders mod, which provides borderless fullscreen feature.
- Added the quick pack mod to optimize datapack / resourcepack zip file loading times for zips with **many** files.

## [1.3.1] - 2026-03-04

### Added

- Added the Gnetum mod (Fabric 1.21.11, NeoForge 1.21.1).
- Added the Ixeris mod (Fabric 1.21.1, Fabric 1.21.11, NeoForge 1.21.1).

### Changed

- Disabled continuous crafting from Inventory Profiles Next by default.
- Disabled MiniHUD main rendering by default; it can be toggled with the `H` key.

### Removed

- Removed the ItemPhysic Lite mod.
- Removed Smooth Scroll from Fabric 1.21.11 due to conflicts with ModernUI smooth scrolling.
- Removed the Remove Reloading Screen mod due to conflicts with ModernUI, which could prevent UI scale adjustment.

### Fixed

- Fixed an issue where the Item Swapper compatibility resource pack was not enabled by default on Fabric 1.21.11.
- Fixed crashes and errors caused by outdated mods.
