# Repository layout / 仓库结构

Python source uses a `src` package. The root commands are compatibility entries; an installed wheel provides `steam-library` and individual executables. The Node bridge and other runtime assets travel with the package. No PyPI release is currently published.

Python 源码采用 `src` 包结构。根目录命令保留为兼容入口，wheel 安装后提供 `steam-library` 及独立命令。Node 桥接和其他运行资源随包分发，目前未发布到 PyPI。

| Location / 位置 | Responsibility / 职责 |
|---|---|
| Eight root CLI files, `_compat.py` | Supported old commands and source bootstrap / 常用旧命令与源码加载 |
| `src/steam_library_toolkit/cli/` | Argument parsing and workflow orchestration / 参数解析与流程编排 |
| `src/steam_library_toolkit/sources/` | Authentication, reconciliation, HTTP workers, metadata, membership and observations / 认证、来源合并、HTTP worker、元数据、成员与观察记录 |
| `src/steam_library_toolkit/classification/` | Rules, corrections, selection, manufacturer fields and tables / 分类规则、校正、选择、厂商字段与表格 |
| `src/steam_library_toolkit/storage/` | Run publication, locks and schema validation / 运行发布、锁与格式校验 |
| `src/steam_library_toolkit/web/` | Read models and loopback server / 展示模型与本地 HTTP 服务 |
| `src/steam_library_toolkit/resources/` | HTML, schemas, built-in rules and production Node bridge / 页面、Schema、内置规则和生产 Node 桥接 |
| `examples/` | Public configuration and correction templates / 可公开的配置与校正模板 |
| Root npm manifests | Single source of Node dependency metadata / Node 依赖元数据的唯一来源 |
| `tools/`, `tests/` | Developer checks, benchmarks and offline regressions / 开发检查、基准与离线回归 |
| `docs/guides/`, `docs/validation/` | Current guides and version-specific evidence / 当前说明与具体版本的验收证据 |
| `docs/releases/`, `releases/` | Plans and machine-readable freezes / 发布计划与机器可读冻结记录 |
| `docs/history/`, `legacy/` | Historical proposals and retired experiments / 历史方案与旧实验 |

## Paths and dependencies / 路径与依赖

`paths.py` separates user data from immutable resources. Source commands keep the checkout root as their default data directory. An installed wheel uses the working directory or `STEAM_LIBRARY_HOME`. Personal configuration and correction filenames remain unchanged. Explicit CLI paths remain relative to the working directory. Keep a `.current.json` pointer together with its hidden `.runs` directory.

`paths.py` 区分用户数据与内置资源。源码运行沿用仓库根目录，wheel 安装后使用当前工作目录或 `STEAM_LIBRARY_HOME`。个人配置和校正文件名不变，显式 CLI 相对路径仍相对于工作目录。`.current.json` 与所引用的隐藏 `.runs` 目录必须一起保留。

The build hook in `setup.py` copies the root npm manifests and canonical [classification guide](guides/CLASSIFICATION_RULES.md) into the wheel. It removes developer shortcuts from the installed npm manifest. These generated copies are not additional tracked sources. `pyproject.toml` defines Python metadata, dependencies and console commands; its development version does not change the frozen release target.

`setup.py` 将根目录 npm 清单及唯一的[分类说明](guides/CLASSIFICATION_RULES.md)复制进 wheel，并移除安装后 npm 清单中的开发快捷命令。生成副本不另行提交。`pyproject.toml` 定义 Python 元数据、依赖与命令，开发版本号不改变冻结的发布目标。

Source Node dependencies use `npm ci`. Wheel users run `steam-library node --install`; the managed directory defaults to `<data directory>/.steam_node`, overridable with `STEAM_LIBRARY_NODE_HOME`. The bridge receives this directory through `NODE_PATH`. Collection never installs dependencies automatically. The HTTP worker runs as a package module with the parent package directory passed to its subprocess, so old source commands also work without an editable install.

源码 Node 依赖使用 `npm ci`；wheel 用户运行 `steam-library node --install`，默认目录为 `<数据目录>/.steam_node`，可用 `STEAM_LIBRARY_NODE_HOME` 更改。桥接通过 `NODE_PATH` 查找依赖，采集不会自动安装。HTTP worker 按包模块启动，父进程传入包目录，使旧源码命令无需 editable 安装也能启动 worker。

## Validation / 验证

See [README](../README.md#contributing) for offline and build checks. `tools/check_distribution.py` compares checkout and sdist-built wheel payloads, installs outside the repository, prepares independent Node dependencies, and exercises saved-library workflows, HTML/API serving and a real HTTP retry. It checks all eight old source entries without editable discovery. This verifies installation behavior, not a new live-account acceptance run.

离线与构建命令见 [README](../README.zh.md#参与贡献)。分发检查比较源码和 sdist 构建的 wheel，在仓库外安装并准备独立 Node 依赖，验证保存库流程、HTML/API 服务和真实 HTTP 重试；也检查八个旧入口在没有 editable 包发现时运行。这是安装行为验证，不是新的真实账号验收。

## Release boundary / 发布边界

This migration is separate from frozen v1.2.0 candidate `044a435a27023034071ac460965b5013fe37df3d`. Its candidate record and validation evidence remain unchanged. A later branch head must not silently replace that target.

本次迁移独立于冻结的 v1.2.0 候选 `044a435a27023034071ac460965b5013fe37df3d`，候选和验收记录保持不变，不得静默用后续分支 HEAD 替代发布目标。
