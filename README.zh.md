# steam-library-toolkit

[![CI](https://github.com/lovewtong/steam-library-toolkit/actions/workflows/tests.yml/badge.svg?branch=main)](https://github.com/lovewtong/steam-library-toolkit/actions/workflows/tests.yml)
[![许可证：MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

> 采集、审计和整理 Steam 游戏库，支持本地浏览与收藏计划导出。

[English](README.md) | **简体中文**

一个使用 Python 和 Node.js 的本地工具：采集 Steam 游戏库、核对数据来源、补全商店信息、人工纠正分类，并在浏览器中筛选游戏。未知值明确保留，每次发布的运行都保存可校验的独立产物。

npm 配置沿用历史私有辅助包名称 `steam-collections`；本项目通过源码仓库使用，不是已发布的 npm 安装包。

## 目录

- [安全](#安全)
- [背景](#背景)
- [安装](#安装)
- [用法](#用法)
- [功能与版本](#功能与版本)
- [支持范围与限制](#支持范围与限制)
- [文档](#文档)
- [维护者](#维护者)
- [参与贡献](#参与贡献)
- [许可证](#许可证)

## 安全

- 不要在 Issue 或 PR 中提交凭据、Cookie、账号配置和个人游戏库明细。`config_local.json`、`*.local.json`、缓存和 `outputs/` 已由 Git 忽略。
- `--local-session` 显式使用当前 Windows 用户的 Steam 本地登录凭据，仅供本次进程使用。扫码授权保存在认可的系统凭据存储中，不回退到明文文件。
- 本地浏览器服务只监听 `127.0.0.1`，仅提供页面与游戏库接口。已验收的 Python 流程不支持自动写回 Steam 收藏。

## 背景

Steam 的 `GetOwnedGames` 可能遗漏客户端中可见的游戏。本项目核对在线客户端清单、许可、Web API 和历史快照，避免把单一接口当成完整游戏库。

项目目标是尽量完整地采集游戏库，让缺失值和来源清晰可查，并让分类结果可以验证、纠正和安全使用。对客户端响应进行核验属于工程保护，不代表已经证明服务端清单绝对完整。

## 安装

### 环境要求

| 组件 | 已验证环境 |
| --- | --- |
| Windows，桌面 Steam 已登录 | 主要真人验收环境，单账号 |
| Python | Windows 真人验收为 3.14.2；离线 CI 为 3.12 |
| Node.js 与 npm | Windows 验收为 Node 22.19.0；CI 为 Node 22 |
| Git | 下方克隆命令需要 |

先安装 [Python](https://www.python.org/downloads/)、[Node.js](https://nodejs.org/en/download) 和 [Git](https://git-scm.com/downloads)。此前声明的 Python 3.10 / Node 18 最低版本没有完成同等验收。

### Windows PowerShell

安装已发布的稳定版本：

```powershell
git clone --branch v1.0.0 https://github.com/lovewtong/steam-library-toolkit.git
cd steam-library-toolkit
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-tested.txt
npm ci
.\.venv\Scripts\python.exe -m pip check
```

后续命令均在项目根目录运行。显式使用虚拟环境路径可避免混用不同 Python。`requirements-tested.txt` 固定直接依赖，不是覆盖全部平台和传递依赖的完整锁文件。

参与开发时，克隆命令可以省略 `--branch v1.0.0`。尚在 PR 中的功能需切换到对应分支，不包含在稳定标签中，见[功能与版本](#功能与版本)。

## 用法

### 采集、补全与浏览

保持桌面 Steam 在线并登录，然后执行：

```powershell
.\.venv\Scripts\python.exe steam_collect.py --local-session --no-store --strict-membership -o outputs/library.json
.\.venv\Scripts\python.exe steam_enrich.py --input outputs/library.json -o outputs/enriched.json
.\.venv\Scripts\python.exe steam_picker.py --serve --input outputs/enriched.json
```

采集会同时生成审计和分类产物。补全请求商店信息，不需要重新登录；大库首次补全可能需要数分钟。最后一条命令会打开本地选游戏页面，在服务终端按 `Ctrl+C` 可停止。

`--strict-membership` 要求实时客户端成员可信，允许辅助来源降级。需要所有已启用的成员来源均成功时，使用 `--strict`。本地凭据不可用时，可将 `--local-session` 替换为 `--login` 进行扫码授权。

### 校正分类与导出计划

按 [AppID 校正规则说明](CLASSIFICATION_OVERRIDES.md) 创建 `classification_overrides.local.json`，再生成独立的校正运行：

```powershell
.\.venv\Scripts\python.exe steam_reclassify.py --input outputs/enriched.json -o outputs/corrected.json
.\.venv\Scripts\python.exe steam_picker.py --serve --input outputs/corrected.json
```

在另一终端中，将 `YOUR_STEAMID64` 替换为采集所用账号：

```powershell
$steamAccount = 'YOUR_STEAMID64'
.\.venv\Scripts\python.exe -B steam_sync_collections.py --input outputs/corrected.json --account $steamAccount --dry-run
.\.venv\Scripts\python.exe -B steam_sync_collections.py --input outputs/corrected.json --account $steamAccount --export-only -o outputs/collections.local.json
```

Dry-run 只预览，不写计划。导出会核验账号、运行、成员和文件哈希，不写入 Steam，也不重新核验当前所有权。补全与重新分类必须使用独立输出名称。

### 命令行

```powershell
.\.venv\Scripts\python.exe steam_collect.py --help
.\.venv\Scripts\python.exe steam_collect.py --diagnose
.\.venv\Scripts\python.exe steam_enrich.py --help
.\.venv\Scripts\python.exe steam_picker.py --help
.\.venv\Scripts\python.exe steam_sync_collections.py --help
```

诊断只检查依赖，不读取凭据或探测网络。账号选择、严格模式、快照、缓存、故障排查和产物结构见[进阶用法](USAGE.zh.md)。

## 功能与版本

| 能力 | 可用版本 |
| --- | --- |
| 客户端库采集、来源审计、未知值记录 | v1.0.0 |
| 商店补全、缓存、有界请求和取消 | v1.0.0 |
| AppID 校正、离线重建、CSV/Markdown、本地浏览 | v1.0.0 |
| 已核验收藏计划预览与导出 | v1.0.0 |
| 分类待复核清单、额外六项 AppID 校正 | 已在 main，包含于尚未发布的 v1.1.0 草稿 |
| 开发商／发行商字段、校正、筛选和计划分组 | 尚未发布，见 [PR #10](https://github.com/lovewtong/steam-library-toolkit/pull/10) |
| 入库日期分组、首次观察时间记录 | 计划中，尚未实现 |

当前已发布版本为 [v1.0.0](https://github.com/lovewtong/steam-library-toolkit/releases/tag/v1.0.0)。[v1.1.0](V1_1_RELEASE_PLAN.md) 仍是草稿，厂商扩展不在其冻结目标内。正式发布状态以 [Releases](https://github.com/lovewtong/steam-library-toolkit/releases) 为准。

在厂商功能分支中，页面新增开发商和发行商筛选；收藏计划支持 `--group-by developers publishers`，以及按精确名称匹配的 `--developer` / `--publisher`。校正示例和验收结果见[厂商维度说明](MANUFACTURER_FACETS.md)。

## 支持范围与限制

- Windows 单账号的采集、补全、校正与撤销、浏览及计划导出已有真实场景验证，见 [Windows 端到端验收](R3_WINDOWS_ACCEPTANCE.md)。
- Windows、Linux、macOS 均执行离线 CI；这**不等于**三个平台都完成了真实账号认证验收。
- 客户端清单一致性检查不能证明 Steam 从不遗漏记录。API／快照降级结果标为候选，未知时长不会被当成零。
- 分类包含启发式规则。样本复核不能证明全库准确率，仍需允许个人校正。
- 多账号切换、Families、退款、临时权益和长期扫码授权仍需更多真实验收。
- 旧 Python 写回已停用；独立 Node／LevelDB 工具未完成同等安全与持久化验收，不属于推荐流程。

## 文档

README 与进阶用法提供中英文对应版本；下方详细设计及验收报告目前主要使用中文。

| 主题 | 文档 |
| --- | --- |
| 进阶命令、文件与故障排查 | [English](USAGE.md) · [简体中文](USAGE.zh.md) |
| 稳定版范围与迁移 | [范围](STABLE_RELEASE_SCOPE.md) · [发布说明](RELEASE_NOTES.md) |
| 元数据补全与字段覆盖 | [补全说明](METADATA_ENRICHMENT.md) |
| 分类与人工校正 | [规则](CLASSIFICATION_RULES.md) · [校正](CLASSIFICATION_OVERRIDES.md) |
| 分类待复核与厂商维度 | [复核清单](CLASSIFICATION_REVIEW_QUEUE.md) · [厂商分类](MANUFACTURER_FACETS.md) |
| 收藏计划验证 | [计划说明](STEAM_SYNC_README.md) |
| 时间字段语义 | [时间契约](TIME_FIELD_CONTRACT.md) |
| 性能与真实场景证据 | [R2 基准](R2_PERFORMANCE_BASELINE.md) · [R3 验收](R3_WINDOWS_ACCEPTANCE.md) |
| 历史审计问题与待验边界 | [整改记录](AUDIT_REMEDIATION.md) |

## 维护者

[@lovewtong](https://github.com/lovewtong)。使用问题和可复现的 Bug 请提交到 [Issues](https://github.com/lovewtong/steam-library-toolkit/issues)。

## 参与贡献

欢迎提交 Issue 和 PR。请说明问题、预期行为及验证方式，区分离线测试与真实 Steam 验证。只提供脱敏诊断，不提交凭据或个人游戏库明细。

修改代码后运行：

```powershell
.\.venv\Scripts\python.exe -B -m unittest discover -s tests -p "test_*.py"
npm test
.\.venv\Scripts\python.exe tools/check_secrets.py
git diff --check
```

中英文 README 和进阶用法需同步维护。行为发生变化时，更新对应契约或验收文档。合并前需要复审，不把未经测试的账号场景写成已支持。

## 许可证

[MIT](LICENSE) © 2026 Steam Collections Contributors。
