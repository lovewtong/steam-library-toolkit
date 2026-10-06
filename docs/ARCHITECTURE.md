# Repository layout / 仓库结构

This is a local Python command-line tool with a Node bridge for Steam client protocols. It is run from a source checkout; there is no installer or published Python package.

项目从源码目录运行：Python 提供命令和本地页面，Node 桥接 Steam 客户端协议。目前没有安装器或已发布的 Python 安装包。

| Location / 位置 | Responsibility / 职责 |
|---|---|
| Root `steam_*.py`, `classify_*.py` | Command entry points and existing Python modules / 命令入口与既有 Python 模块 |
| `node_bridge/` | Runtime client, license, family and playtime adapters / 产品运行所需的客户端、许可、家庭与时长适配 |
| `tools/` | Development checks, benchmarks and inspection scripts / 开发检查、基准与辅助脚本 |
| `tests/`, `tests/fixtures/` | Offline regressions and public fixtures / 离线回归与可公开测试样本 |
| `schemas/` | Stored artifact contracts / 保存产物的格式契约 |
| `docs/guides/` | Current feature guides / 当前功能说明 |
| `docs/validation/` | Reviews and acceptance evidence / 复审与验收记录 |
| `docs/releases/`, `releases/` | Version plans and machine-readable freeze records / 版本计划与机器可读冻结记录 |
| `docs/history/`, `legacy/` | Historical proposals and retired experiments / 历史方案与旧实验工具 |

Configuration, personal corrections, caches and outputs keep their existing paths. These are local files, not source assets. A `.current.json` pointer and the hidden `.runs` directory it references belong together; directory cleanup must not separate them.

个人配置、校正规则、缓存和输出保持原路径。它们属于本地数据，不是源码资源。`.current.json` 与所引用的隐藏 `.runs` 目录必须一起保留，整理时不能拆散。

Run the offline checks from the repository root:

```powershell
.\.venv\Scripts\python.exe -B -m unittest discover -s tests -p "test_*.py"
npm test
.\.venv\Scripts\python.exe tools/check_secrets.py
.\.venv\Scripts\python.exe tools/check_docs.py
git diff --check
```

The document check validates relative file targets. It does not test URL availability, heading anchors or whether historical statements still describe the current release.

文档检查验证相对链接的目标文件，不验证外部 URL、标题锚点或历史表述是否适用于当前版本。

## Release boundary / 发布边界

This reorganization is separate from the frozen v1.2.0 candidate `044a435a27023034071ac460965b5013fe37df3d`. The candidate and its validation records remain unchanged. A later branch head must not silently replace that release target.

结构整理独立于已冻结的 v1.2.0 候选 `044a435a27023034071ac460965b5013fe37df3d`。候选和对应验收记录保持不变，不得静默用后续分支 HEAD 替代发布目标。
