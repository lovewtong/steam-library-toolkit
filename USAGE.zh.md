# 进阶用法

[中文 README](README.zh.md) · [English](USAGE.md)

在项目根目录运行命令。示例使用 README 中创建的 Windows 虚拟环境和当前 `main` 分支，账号和机器名占位符需自行替换。旧版本没有的功能另行标注。

## 账号与来源

```powershell
# 仅本次进程复用 Windows 本地凭据，不保存。
.\.venv\Scripts\python.exe steam_collect.py --local-session --no-store --account YOUR_STEAMID64 -o outputs/library.json
# 或使用 Steam 手机 App 扫码，将授权保存在系统密钥环。
.\.venv\Scripts\python.exe steam_collect.py --login --no-store -o outputs/library.json
# 复用此前已保存的扫码授权。
.\.venv\Scripts\python.exe steam_collect.py --no-store -o outputs/library.json
```

客户端认证不强制要求 `config_local.json`。仅使用 API 时，复制 `config_local.example.json`，在本地填写 API Key 和 SteamID64。API-only 结果属于候选，不是已核验的当前客户端库。`--account` 覆盖配置中的账号，来源账号不一致会拒绝合并；不同账号使用独立输出目录。

`--machine MACHINE_NAME` 显式选择在线客户端；默认选择本机，不会随意选另一台设备。桌面已登录不代表辅助进程可以跳过自己的服务器连接和认证。

| 参数 | 行为 |
| --- | --- |
| `--strict-membership` | 要求客户端和已启用家庭来源可信，允许辅助来源降级 |
| `--strict` | 要求当前客户端和所有已启用的成员来源成功 |
| `--require-source web_api` | 额外要求指定辅助来源成功，可重复 |
| `--source client` | 选择客户端采集 |
| `--source api` | 仅使用 API，生成候选成员 |
| `--owned-only` | 使用传统 API 过滤，不保证完整性 |
| `--no-store` | 跳过商店元数据请求 |
| `--no-family` | 显式限定为客户端成员，需独立输出路径 |

`main` 的客户端采集还会核验家庭来源，加入符合共享资格的游戏。家庭核验失败会阻止发布；明确未加入家庭属于成功的空来源。可使用 `--require-source family_library`。详见[家庭采集](docs/guides/STEAM_FAMILIES.md)。严格成员策略不要求可选的元数据和时长来源成功。`--strict` 失败不会切换原有 current 指针。

## 候选数据与完整性

`GetClientAppList` 会检查响应结构、账号、机器会话和两次相同的 AppID 集合，但没有能证明语义完整性的协议完成标记。相对同账号上次客户端库或客户端与家庭合并库，未解释的移除比例超过 20% 会阻止发布；应核对变化后再调整 `--max-unexplained-removal-ratio`。

实时客户端不可用时，可由账号匹配快照或 Web API 提供历史／候选记录，默认写入独立 `.candidates.json` 目标和指针。`--allow-candidates` 允许将候选发布到指定路径；`--allow-candidate-membership` 则独立控制实验性的许可候选并集。两者都不能证明当前所有权。

## 快照

```powershell
.\.venv\Scripts\python.exe steam_collect.py --local-session --no-store --snapshot-out outputs/library.snapshot.json -o outputs/library.json
# 以下参数组合为离线导入，不使用凭据或网络。
.\.venv\Scripts\python.exe steam_collect.py --apps-file outputs/library.snapshot.json --no-api --no-store -o outputs/imported.json
```

快照保留账号、观察时间、完整性证据、条数和校验和。旧 `AppID 名称` 文本无法核验身份或年龄。快照的新鲜度描述数据年龄，不表示所有权是否已过期。

## 补全与缓存

```powershell
.\.venv\Scripts\python.exe steam_enrich.py --input outputs/library.json -o outputs/enriched.json --workers 2
.\.venv\Scripts\python.exe steam_enrich.py --input outputs/library.json -o outputs/sample.json --appid 550 --appid 730
.\.venv\Scripts\python.exe steam_enrich.py --input outputs/enriched.json -o outputs/refreshed.json --refresh-metadata --cache-dir outputs/store-cache
```

输入必须有有效运行指针和可信客户端成员，输出必须独立。`--appid` 限制请求范围，不限制输出成员。补全保留成员、应用类型、时长证据及原始采集时间，不重新核验所有权。

并发数为 1–4，共享请求启动间隔与冷却。缺失或非法字段保留旧值，明确空数组可以替换旧数组。请求成功不代表字段齐全；`metadata.state=partial` 表示请求覆盖不完整，不会因此删除游戏。

成功响应缓存七天，`not_found` 缓存六小时，临时错误使用更短有效期。未找到不代表永久下架。当前 `main` 使用缓存 v6，旧条目按需重取；已发布版本使用各自的缓存格式。详见[元数据语义](docs/guides/METADATA_ENRICHMENT.md)。

## 数据文件与备份

以 `-o outputs/library.json` 为例：

```text
outputs/
├── library.json                  # 兼容导出
├── library.audit.json            # 兼容审计导出
├── library.current.json          # 已提交运行的指针和哈希
└── .library.runs/
    └── <run_id>/                 # 游戏库、审计、分类和报告
```

整轮运行完成校验并持久化后才切换指针，读取时核验哈希并使用同一运行的产物。备份需同时保留**指针及其引用的隐藏运行目录**，单独复制平面 JSON 不构成已核验运行。不要编辑已有运行内部文件。

运行包含 `steam_library.audit.json`、`classified.json`、`classified.csv`、`classified.md`、`steam_library_classified.json`、实际校正规则、摘要以及可用快照／探测报告。此示例的失败诊断写到独立 `outputs/.library.failed-runs/` 目录。进程退出后锁文件可能保留，操作系统锁会释放；旧运行不会自动清理。

## 分类与浏览

```powershell
.\.venv\Scripts\python.exe classify_games.py -i outputs/enriched.json
.\.venv\Scripts\python.exe classify_steam_games.py -i outputs/enriched.json
.\.venv\Scripts\python.exe classify_games.py -i outputs/enriched.json --include-type game,demo
.\.venv\Scripts\python.exe steam_picker.py --input outputs/enriched.json --name BioShock --list
.\.venv\Scripts\python.exe steam_picker.py --serve --input outputs/enriched.json --port 8765 --no-browser
```

默认只分类明确为 `game` 的记录；`--include-type all` 包含其他和未知类型。候选输入需显式加 `--allow-candidates`。独立分类脚本写出平面文件，不会替换已核验运行中的冻结分类；需要应用校正时，用 `steam_reclassify.py` 生成新运行。

无论阅读哪种语言的文档，当前页面分类标签都使用中文。发布新运行后刷新浏览器。`--open INDEX` 会在 Steam 中启动游戏，不是预览操作。

分类复核清单已在 main 和 v1.1.0 中，v1.0.0 不包含此命令：

```powershell
.\.venv\Scripts\python.exe steam_review_classification.py --input outputs/enriched.json
```

开发商／发行商筛选、首次观察日期和家庭采集已在 `main`，v1.0.0 和 v1.1.0 不包含这些功能，用法见[厂商说明](docs/guides/MANUFACTURER_FACETS.md)和[时间分类](docs/guides/TIME_CLASSIFICATION.md)。收藏计划使用 README 中的命令预览和导出，不要交给旧 Node 写回工具。

## 证据与故障排查

应用类型参考客户端、PICS、商店／缓存及历史证据，不能确认时保持未知。时长逐字段保留来源与冲突，区分未知、已知零值和历史值。客户端清单稳定不能解决所有未知时长，也不能证明库全集。

| 现象 | 检查方向 |
| --- | --- |
| `PYTHON_DEPENDENCY_MISSING` | 用运行脚本的同一个虚拟环境 Python 安装依赖 |
| `CLIENT_AUTH_UNAVAILABLE` | 桌面登录不一定有可复用缓存；检查所选账号，或改用 `--login` |
| `CM_CONNECT_TIMEOUT` / `WEB_SESSION_TIMEOUT` | 查看当前阶段与已有网络／代理配置；两者代表不同失败阶段 |
| `OUTPUT_BUSY` | 另一个进程持有输出锁，不要通过删除文件绕过 |
| 页面拒绝候选库 | 获取可信客户端运行，或显式允许浏览候选 |
| 元数据未知或补全为 `partial` | 查看逐应用字段状态和来源错误；缺失不等于不支持 |
| 页面仍显示旧数据 | 核对 `--input`、current 指针并刷新；平面文件不会替换已核验运行 |
| 家庭共享游戏缺失 | v1.1.0 没有家庭来源；`main` 核验并合入符合共享资格的游戏，接口成功仍不证明全集覆盖。详见[家庭采集](docs/guides/STEAM_FAMILIES.md) |

可先运行 `--diagnose` 进行不读取凭据、不联网的检查。已配置的 HTTP(S) 代理会被使用，但不会打印地址或密码。不要分享含密钥的原始认证或代理诊断。详细说明见[审计整改](docs/validation/AUDIT_REMEDIATION.md)、[时间语义](docs/guides/TIME_FIELD_CONTRACT.md)和[版本迁移](RELEASE_NOTES.md)。
