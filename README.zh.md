# steam-library-toolkit

[![CI](https://github.com/lovewtong/steam-library-toolkit/actions/workflows/tests.yml/badge.svg?branch=main)](https://github.com/lovewtong/steam-library-toolkit/actions/workflows/tests.yml)
[![许可证：MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

> 采集、审计和整理 Steam 游戏库，支持本地浏览与收藏计划导出。

[English](README.md) | **简体中文**

把 Steam 游戏库导出到本地，补全商店信息，再按玩法、氛围、开发商或发行商筛选。分类不合适时，可以按 AppID 修改规则，也可以将结果导出为收藏计划。

## 目录

- [安全](#安全)
- [背景](#背景)
- [安装](#安装)
- [用法](#用法)
- [版本](#版本)
- [已知限制](#已知限制)
- [文档](#文档)
- [维护者](#维护者)
- [参与贡献](#参与贡献)
- [许可证](#许可证)

## 安全

账号配置放在 `config_local.json`，个人分类规则放在 `classification_overrides.local.json`，这两个文件都已加入 Git 忽略列表。提交问题时，请去掉凭据、Cookie 和个人游戏库数据。

浏览页面只在 `127.0.0.1` 提供服务。本地登录使用已有 Steam 凭据，仅用于当前进程；扫码授权保存在系统凭据存储中。

## 背景

项目最初解决两个问题：`classify_games.py` 缺少运行入口，以及 `GetOwnedGames` 会漏掉部分客户端可见的游戏。现在采集会结合在线客户端清单、许可、Web API 和快照。审计文件记录各来源是否成功，以及字段的来源。

## 安装

使用 Windows，安装并登录 Steam。项目已在 Python 3.12／3.14 和 Node.js 22 下测试。需要安装环境时，可访问 [Python](https://www.python.org/downloads/)、[Node.js](https://nodejs.org/en/download) 和 [Git](https://git-scm.com/downloads) 下载页面。

在 PowerShell 中执行：

```powershell
git clone --branch v1.3.0 https://github.com/lovewtong/steam-library-toolkit.git
cd steam-library-toolkit
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-tested.txt
.\.venv\Scripts\python.exe -m pip install -e . --no-deps
npm ci
```

上面的命令选择稳定版 v1.3.0 标签，包含厂商筛选、首次观察日期、家庭采集和安装后的命令。旧版 v1.2.0 使用根目录脚本，没有 `pyproject.toml`；使用旧标签时，请按该版本自己的 README 操作。

也可以用 `python -m pip install .` 安装这份源码，再运行 `steam-library collect`、`steam-library enrich`、`steam-library picker` 等命令；完整列表见 `steam-library --help`。从 wheel 安装后，用 `steam-library node --install` 准备 Node 依赖。目前没有发布到 PyPI。版本 `1.3.0` 已在 `09b6d4a` 正式发布，wheel 和源码归档可从 [v1.3.0](https://github.com/lovewtong/steam-library-toolkit/releases/tag/v1.3.0) 下载。详见[候选记录](releases/v1.3.0-candidate.json)和[升级／回退验收](docs/validation/V1_3_RELEASE_ACCEPTANCE.md)。

源码运行时，默认配置、缓存和输出仍位于仓库根目录；wheel 安装后默认使用当前工作目录。启动命令前设置 `STEAM_LIBRARY_HOME` 可选择其他数据目录，显式 `--input`、`--output` 路径按原有方式处理。详见[安装后的用法](USAGE.zh.md#安装后的命令与数据目录)。

## 用法

以下命令都在项目根目录运行，保持 Steam 在线并登录。

### 采集与浏览

```powershell
.\.venv\Scripts\python.exe steam_collect.py --local-session --no-store --strict-membership -o outputs/library.json
.\.venv\Scripts\python.exe steam_enrich.py --input outputs/library.json -o outputs/enriched.json
.\.venv\Scripts\python.exe steam_picker.py --serve --input outputs/enriched.json
```

第一条命令采集游戏库，同时生成审计和分类文件；第二条补全商店信息。大库第一次补全可能需要几分钟，后续会复用缓存。最后一条打开浏览页面，在终端按 `Ctrl+C` 停止服务。

`--strict-membership` 要求取得实时客户端清单，并成功核验家庭来源。只采集客户端时，使用 `--no-family` 和独立输出路径。本地认证失败时，把 `--local-session` 换成 `--login`，改用扫码登录。

### 修改分类

按[校正规则说明](docs/guides/CLASSIFICATION_OVERRIDES.md)填写 `classification_overrides.local.json`，然后生成新结果：

```powershell
.\.venv\Scripts\python.exe steam_reclassify.py --input outputs/enriched.json -o outputs/corrected.json
.\.venv\Scripts\python.exe steam_picker.py --serve --input outputs/corrected.json
```

还可以查看需要复核的分类：

```powershell
.\.venv\Scripts\python.exe steam_review_classification.py --input outputs/corrected.json
```

### 导出收藏计划

在另一个终端中，填写采集账号的 SteamID64：

```powershell
$steamAccount = 'YOUR_STEAMID64'
.\.venv\Scripts\python.exe -B steam_sync_collections.py --input outputs/corrected.json --account $steamAccount --dry-run
.\.venv\Scripts\python.exe -B steam_sync_collections.py --input outputs/corrected.json --account $steamAccount --export-only -o outputs/collections.local.json
```

`--dry-run` 预览计划，`--export-only` 保存 JSON。导出前会检查保存的账号、游戏库和文件哈希，目前不写入 Steam 收藏。

加入 `--group-by developers publishers` 可按厂商分组；`--developer "NAME"`／`--publisher "NAME"` 按完整名称筛选。

可以用 `--first-seen-year 2026 --first-seen-month 10` 按年月筛选，计划支持 `first_seen_year`／`first_seen_month` 分组。这是保存记录中首次观察到客户端或家庭成员的时间，不是购买日期。历史继承和未知值说明见[时间分类](docs/guides/TIME_CLASSIFICATION.md)。

### 帮助

每个脚本都支持 `--help`。遇到依赖问题，可以先运行：

```powershell
.\.venv\Scripts\python.exe steam_collect.py --diagnose
```

这个检查不需要联网。账号选择、快照、缓存设置和故障排查见[进阶用法](USAGE.zh.md)。备份结果时，请同时保留 `.current.json` 指针及其引用的隐藏运行目录。

## 版本

[v1.3.0](https://github.com/lovewtong/steam-library-toolkit/releases/tag/v1.3.0) 是当前已发布版本，固定在 `09b6d4a`，在既有采集、审计、补全、校正、浏览和计划导出流程上，增加 wheel/sdist 打包、安装后的命令和构建追溯。

稳定使用时请选择版本标签，`main` 可能包含后续改动。下载见 [Releases](https://github.com/lovewtong/steam-library-toolkit/releases)。

[v1.3.0 范围](docs/releases/V1_3_RELEASE_PLAN.md)包含包安装和构建追溯。候选 `09b6d4a` 已通过升级／回退与发布验收，六个附件的匿名下载均与冻结哈希一致。

冻结范围、升级验收和发布核验见[发布计划](docs/releases/V1_3_RELEASE_PLAN.md)、[发布说明](RELEASE_NOTES.md)和[发布记录](releases/v1.3.0-publication.json)。

## 已知限制

- 实时采集已在 Windows 单账号环境测试。Linux 和 macOS 有自动化测试，真实账号登录仍待测试。
- Steam 各来源可能有差异或遗漏。API 和快照降级数据会标为候选；缺失的时长和元数据保留为未知。
- 分类规则可能需要人工调整。开发商和发行商名称默认使用商店信息，也可以自行校正。
- 多账号切换和临时权益还需要更多测试。目前浏览页面的分类标签使用中文。
- v1.1.0 可能漏掉 Steam Families 游戏。v1.2.0 加入了经过核验的家庭来源，见[家庭采集](docs/guides/STEAM_FAMILIES.md)和[账号场景](docs/validation/REAL_SCENARIO_VALIDATION.md)；仍不保证全家庭游戏完整或当前均可启动。
- 收藏计划仅支持导出，旧 Node／LevelDB 写回脚本不在支持流程内。
- 暂时无法提供准确购买日期。首次观察日期只描述工具可取得的历史记录。

## 文档

- [文档索引](docs/README.md)
- [进阶用法](USAGE.zh.md) · [Advanced usage](USAGE.md)
- [分类规则](docs/guides/CLASSIFICATION_RULES.md) · [个人校正](docs/guides/CLASSIFICATION_OVERRIDES.md) · [复核清单](docs/guides/CLASSIFICATION_REVIEW_QUEUE.md)
- [元数据补全](docs/guides/METADATA_ENRICHMENT.md) · [开发商与发行商](docs/guides/MANUFACTURER_FACETS.md)
- [收藏计划](docs/guides/STEAM_SYNC_README.md) · [时间字段](docs/guides/TIME_FIELD_CONTRACT.md) · [时间分类](docs/guides/TIME_CLASSIFICATION.md)
- [发布说明](RELEASE_NOTES.md) · [稳定版范围](docs/releases/STABLE_RELEASE_SCOPE.md)
- 测试记录：[性能](docs/validation/R2_PERFORMANCE_BASELINE.md)、[Windows 使用流程](docs/validation/R3_WINDOWS_ACCEPTANCE.md)、[Bug 修复](docs/validation/AUDIT_REMEDIATION.md)
- [当前账号场景](docs/validation/REAL_SCENARIO_VALIDATION.md) · [v1.3.0 范围](docs/releases/V1_3_RELEASE_PLAN.md)

详细说明和测试记录目前主要使用中文。

## 维护者

[@lovewtong](https://github.com/lovewtong)。问题和建议可以提交到 [Issues](https://github.com/lovewtong/steam-library-toolkit/issues)。

## 参与贡献

报告问题时，请附上执行的命令、预期结果和错误信息。欢迎提交 PR。修改代码后运行：

```powershell
.\.venv\Scripts\python.exe -B -m unittest discover -s tests -p "test_*.py"
npm test
.\.venv\Scripts\python.exe tools/check_secrets.py
.\.venv\Scripts\python.exe tools/check_docs.py
.\.venv\Scripts\python.exe -m pip install build==1.6.1
.\.venv\Scripts\python.exe tools/check_distribution.py
git diff --check
```

修改命令或功能时，请同步中英文 README 和使用说明。

根目录的八个 Python 命令保留为兼容入口。实现位于 `src/steam_library_toolkit/`，其中 `resources/` 保存页面、Schema、内置规则和 Node 桥接；示例在 `examples/`，开发脚本在 `tools/`，旧实验工具在 `legacy/`。详见[仓库结构](docs/ARCHITECTURE.md)。

## 许可证

[MIT](LICENSE) © 2026 Steam Collections Contributors。
