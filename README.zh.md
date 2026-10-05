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
git clone https://github.com/lovewtong/steam-library-toolkit.git
cd steam-library-toolkit
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-tested.txt
npm ci
```

这里安装的是 `main`，包含开发商／发行商筛选。如果要使用已发布的 v1.0.0，在克隆命令中加入 `--branch v1.0.0`；该版本不包含厂商筛选和分类复核清单。

## 用法

以下命令都在项目根目录运行，保持 Steam 在线并登录。

### 采集与浏览

```powershell
.\.venv\Scripts\python.exe steam_collect.py --local-session --no-store --strict-membership -o outputs/library.json
.\.venv\Scripts\python.exe steam_enrich.py --input outputs/library.json -o outputs/enriched.json
.\.venv\Scripts\python.exe steam_picker.py --serve --input outputs/enriched.json
```

第一条命令采集游戏库，同时生成审计和分类文件；第二条补全商店信息。大库第一次补全可能需要几分钟，后续会复用缓存。最后一条打开浏览页面，在终端按 `Ctrl+C` 停止服务。

`--strict-membership` 要求取得实时客户端清单。本地认证失败时，把 `--local-session` 换成 `--login`，改用扫码登录。

### 修改分类

按[校正规则说明](CLASSIFICATION_OVERRIDES.md)填写 `classification_overrides.local.json`，然后生成新结果：

```powershell
.\.venv\Scripts\python.exe steam_reclassify.py --input outputs/enriched.json -o outputs/corrected.json
.\.venv\Scripts\python.exe steam_picker.py --serve --input outputs/corrected.json
```

使用 `main` 时，还可以查看需要复核的分类：

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

在 `main` 中，加入 `--group-by developers publishers` 可按厂商分组；`--developer "NAME"`／`--publisher "NAME"` 按完整名称筛选。

### 帮助

每个脚本都支持 `--help`。遇到依赖问题，可以先运行：

```powershell
.\.venv\Scripts\python.exe steam_collect.py --diagnose
```

这个检查不需要联网。账号选择、快照、缓存设置和故障排查见[进阶用法](USAGE.zh.md)。备份结果时，请同时保留 `.current.json` 指针及其引用的隐藏运行目录。

## 版本

[v1.0.0](https://github.com/lovewtong/steam-library-toolkit/releases/tag/v1.0.0) 是当前已发布版本，包含采集、审计、元数据补全、分类校正、本地浏览和收藏计划导出。

`main` 还包含分类复核清单、额外六项 AppID 校正，以及开发商／发行商字段、筛选和计划分组，这些改动尚未发布。[v1.1.0 草稿](V1_1_RELEASE_PLAN.md)包含复核清单与分类校正，厂商功能另行发布。已发布版本见 [Releases](https://github.com/lovewtong/steam-library-toolkit/releases)。

## 已知限制

- 实时采集已在 Windows 单账号环境测试。Linux 和 macOS 有自动化测试，真实账号登录仍待测试。
- Steam 各来源可能有差异或遗漏。API 和快照降级数据会标为候选；缺失的时长和元数据保留为未知。
- 分类规则可能需要人工调整。开发商和发行商名称默认使用商店信息，也可以自行校正。
- 多账号切换、Steam Families 和临时权益还需要更多测试。目前浏览页面的分类标签使用中文。
- 收藏计划仅支持导出，旧 Node／LevelDB 写回脚本不在支持流程内。
- 尚未实现按入库日期分组。

## 文档

- [进阶用法](USAGE.zh.md) · [Advanced usage](USAGE.md)
- [分类规则](CLASSIFICATION_RULES.md) · [个人校正](CLASSIFICATION_OVERRIDES.md) · [复核清单](CLASSIFICATION_REVIEW_QUEUE.md)
- [元数据补全](METADATA_ENRICHMENT.md) · [开发商与发行商](MANUFACTURER_FACETS.md)
- [收藏计划](STEAM_SYNC_README.md) · [时间字段](TIME_FIELD_CONTRACT.md)
- [发布说明](RELEASE_NOTES.md) · [稳定版范围](STABLE_RELEASE_SCOPE.md)
- 测试记录：[性能](R2_PERFORMANCE_BASELINE.md)、[Windows 使用流程](R3_WINDOWS_ACCEPTANCE.md)、[Bug 修复](AUDIT_REMEDIATION.md)

详细说明和测试记录目前主要使用中文。

## 维护者

[@lovewtong](https://github.com/lovewtong)。问题和建议可以提交到 [Issues](https://github.com/lovewtong/steam-library-toolkit/issues)。

## 参与贡献

报告问题时，请附上执行的命令、预期结果和错误信息。欢迎提交 PR。修改代码后运行：

```powershell
.\.venv\Scripts\python.exe -B -m unittest discover -s tests -p "test_*.py"
npm test
.\.venv\Scripts\python.exe tools/check_secrets.py
git diff --check
```

修改命令或功能时，请同步中英文 README 和使用说明。

## 许可证

[MIT](LICENSE) © 2026 Steam Collections Contributors。
