# v1.3.0 — 安装包、命令入口与构建追溯 / Packaging, commands and build provenance

[中文](#中文) · [English](#english)

版本准备：`1.3.0`。完整候选提交、tree、构建哈希与最终验收会在冻结记录和 Release 草稿中另行给出；不自动采用后续 main HEAD。当前尚未公开本版本。v1.2.0 保持固定在 `044a435a27023034071ac460965b5013fe37df3d`。

## 中文

### 相对 v1.2.0 的变化

- 实现位于 `src/steam_library_toolkit`，HTML、Schema、内置规则和 Node 桥接作为安装资源交付。提供 wheel 和 sdist，可安装后使用 `steam-library`、直接 executable 和 `python -m steam_library_toolkit`。
- 八个常用根目录 Python 命令继续兼容。旧内部根目录模块不是公开导入接口，集成代码请改用包模块。
- 安装版默认在工作目录保存配置与数据，`STEAM_LIBRARY_HOME` 可选择独立目录。内置资源保留在安装目录，个人校正文件放在数据目录。
- `steam-library node --install` 使用随包锁文件显式准备 Node 依赖到数据目录下 `.steam_node`；源码环境继续使用 `npm ci`。安装依赖本身不认证 Steam。
- producer 新增包版本、构建身份和校验状态。安装内容被修改或记录无效时，不提供原构建标识；旧运行、旧 wheel 与 parent_run 保留原有证据。安装版不猜测当前目录的 Git 提交。
- 延续采集、审计、补全、分类校正、浏览、收藏计划导出，以及厂商、首次观察和家庭成员规则。本版不添加新的分类或成员来源。

### 安装、升级和回退

需要 Python 3.12+ 与 Node；Windows 真人验收使用 Python 3.14.2、Node 22.19.0，三平台离线 CI 使用 Python 3.12、Node 22。其他系统真人认证仍未验收。无 PyPI、自动安装器或自动更新。

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install .\steam_library_toolkit-1.3.0-py3-none-any.whl
$steamCli = (Resolve-Path .\.venv\Scripts\steam-library.exe).Path
$env:STEAM_LIBRARY_HOME = 'C:\SteamLibraryData'
New-Item -ItemType Directory -Force $env:STEAM_LIBRARY_HOME
Set-Location $env:STEAM_LIBRARY_HOME
& $steamCli node --install
& $steamCli collect --local-session --no-store --strict --strict-membership -o library.json
```

开始升级前保留旧软件、完整数据目录、current 指针及隐藏运行目录、配置和个人校正。先用新环境读取备份并写到独立输出，核对数量、未知字段与历史，再决定迁移。不得只复制表面的 JSON 并丢弃隐藏运行目录。回退使用旧软件＋其对应旧数据备份；不承诺旧软件可以读任意新运行格式。

安装目录不是数据目录，修改内置文件会改变构建校验状态。用 pip 升级 Python 包不会自动迁移数据，也不会自动替换独立 Node 目录；跨版本迁移时在独立数据／Node 目录准备依赖，再切换。

### 验收边界

开发提交的 180 Python／36 Node、三平台构建回归及 Windows 单账号家庭测试已记录；正式候选需重新绑定其版本、SHA 和安装包验收。此前的 829 条、818 game、441 共享和 460 未知时长不是新候选的自动保证。

不承诺全集或全家庭完整性、逐游戏可启动、多账号切换、离线恢复、自然权益变化、全库分类准确率或跨系统真人认证。首次观察不是购买日期；共享库时长不是本人时长。收藏功能仍为 dry-run／计划导出，没有启用 Steam 写回。

## English

v1.3.0 packages implementation under `src/steam_library_toolkit` and distributes rules, schemas, HTML and the Node bridge with wheel/sdist artifacts. Installed handlers support `steam-library`, direct executables and `python -m steam_library_toolkit`. Eight common root Python commands remain compatible; old internal root imports are not public APIs.

Wheel installations keep user data in the working directory or `STEAM_LIBRARY_HOME`, separate from installed resources. `steam-library node --install` explicitly prepares locked Node dependencies in the data directory; source checkouts continue to use `npm ci`. There is no PyPI publication, installer or auto-update.

Producer evidence now includes package version, verified payload identity and status. Invalid or modified installations do not claim the original ID. Old runs, wheels and historical parent producers remain compatible; installed runs do not infer Git provenance from the working directory. Hashes support traceability and integrity checks, not digital signatures.

Python 3.12+ is required. Offline CI runs on Windows/Linux/macOS using Python 3.12 and Node 22; live Windows acceptance uses Python 3.14.2 and Node 22.19.0. Other-platform authentication remains unverified.

Before upgrading, preserve old software and the entire data directory, including current pointers, hidden generations, configuration and personal corrections. Test the new environment against a backup with separate output. Roll back with old software plus its preserved old data; arbitrary forward compatibility is not promised. Python package upgrades do not migrate data or automatically replace a separate Node runtime.

Collection, audit, enrichment, corrections, browsing, export-only plans, manufacturer filters, first-observation dates and checked family membership are inherited. No new acquisition source or classification batch is added. Development-commit results are not automatic acceptance of the final candidate. Exhaustive membership, launches, multiple accounts, offline recovery, entitlement changes and global classification accuracy remain outside the validated claims. No Steam collection writes are enabled.

See [v1.3.0 scope](docs/releases/V1_3_RELEASE_PLAN.md), [build provenance](docs/guides/BUILD_PROVENANCE.md), [usage](USAGE.md) / [中文用法](USAGE.zh.md), and the preserved [v1.2.0 notes](docs/releases/V1_2_RELEASE_NOTES.md).
