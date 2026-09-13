# Steam 游戏库本地采集与自动分类

English: [README_EN.md](README_EN.md)

## 如何实现自动分类（推荐流程）

不写 Steam 内部文件、不依赖写回收藏，用本地脚本完成「自动分类 + 按分类选游戏」：

| 步骤 | 命令 | 说明 |
|------|------|------|
| 1. 有游戏库数据 | `python steam_collect.py --local-session --no-store --strict` | Windows 已登录 Steam；其他授权方式见安装说明 |
| 2. 分类产物 | 采集时自动生成 | 保存到同一运行目录；独立分类命令仍可导出表格 |
| 3. 按分类用 | `python steam_picker.py --serve` | 浏览器里按 核心玩法/强度/氛围 筛选，点「在 Steam 中打开」启动 |

**打开选游戏页（采集已发布时）：**

```bash
cd /path/to/steam-library-toolkit
python steam_picker.py --serve
```

**采集完成后直接打开选游戏页，刷新会读取最新运行：**

```bash
python steam_picker.py --serve
```

分类结果只存在本地 JSON 里，Steam 客户端不显示这些分组，但通过 **steam_picker 网页** 或 **命令行** 可以按分类筛选并启动游戏，等同于「自动分类可用」。

---

## 流程概览

```
扫码授权 / 显式本机登录态 / 可选 API 配置
        ↓
  steam_collect.py  →  steam_library.json
        ↓
  classify_steam_games.py →  steam_library_classified.json（五维分类）
        ↓
  steam_picker.py --serve  →  浏览器按分类选游戏、用 Steam 启动

（可选）classify_games.py →  game_library_classified.csv / .md
```

## 1. 安装与账号授权

需要 Python 3.10+、Node.js 18+：

```bash
python -m pip install -r requirements.txt
npm ci
```

Windows 也可以使用项目独立环境，避免 `pip` 与运行脚本的 Python 不一致：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
npm ci
.\.venv\Scripts\python.exe steam_collect.py --local-session --no-store --strict
```

使用此环境时，将后续命令里的 `python` 替换为 `.\.venv\Scripts\python.exe`。缺少 `vdf` 会提示 `PYTHON_DEPENDENCY_MISSING`；这不表示 Steam 没有登录。扫码授权还需要 `keyring`。

运行后会立即显示凭据读取、网络模式与当前采集阶段，等待期间每 10 秒报告一次。桌面 Steam 已登录后，脚本仍需建立自己的服务器连接；连接超过 60 秒会报 `CM_CONNECT_TIMEOUT`，认证成功后缺少网页授权会报 `WEB_SESSION_TIMEOUT`。检测到的 HTTP(S) 代理用于客户端连接、扫码认证及后续 Web 请求，日志不显示代理地址或密码。按 Ctrl+C 会清理采集子进程并正常报告中断；看到 `KeyboardInterrupt` 只说明旧版运行被中断，不能据此判断登录失效。

推荐先启动桌面 Steam，再用手机 Steam App 扫码授权：

```bash
python steam_collect.py --login --no-store
```

授权仅保存在操作系统凭据存储（Windows Credential Manager、macOS Keychain 或支持的 Linux 密钥环）。后续运行不需要重复扫码。密钥环不可用时会报错，不回退到明文凭据文件。

Windows 已登录 Steam 时，也可显式复用本机当前账号，凭据仅用于本次进程，不保存：

```powershell
python steam_collect.py --local-session --no-store
```

该路径通过当前 Windows 用户的 DPAPI 解密 Steam 本地登录凭据，需要 Steam 正在登录且存在可用缓存。客户端格式可能变化，失败时可改用 `--login`。

`config_local.json` 现在是可选配置。仅使用 Web API 时，复制 `config_local.example.json`，填写 `steam_api_key` 和 `steam_id`；客户端认证成功时不需要 API Key。`--account STEAMID64` 可显式覆盖配置账号，快照与认证账号不匹配会拒绝合并。多个在线设备可用 `--machine 机器名` 选择，默认本机，不会自动挑选另一台设备。

## 2. 采集游戏库

```bash
# 使用已保存的扫码授权；默认同时读取客户端、许可和 Web API
python steam_collect.py --no-store
# 数据源失败时停止，保留原输出；适合定期更新
python steam_collect.py --local-session --no-store --strict
# 可选：补充商店类型、分类、多人和手柄信息
python steam_collect.py --local-session
```

已用 `--no-store` 采集后，可独立补全商店信息，无需重新认证 Steam：

```powershell
python steam_enrich.py --input steam_live_test.json -o steam_enriched.json
python steam_picker.py --serve --input steam_enriched.json
# 可先只补全库中指定应用（参数可重复）
python steam_enrich.py --input steam_live_test.json -o steam_enriched_sample.json --appid 550
```

可用 `classification_overrides.local.json` 按 AppID 人工校正，并通过 `python steam_reclassify.py --input steam_enriched.json -o steam_reclassified.json` 离线重建。两种分类输出共享校正，旧运行保持不变。格式与映射见 [CLASSIFICATION_OVERRIDES.md](CLASSIFICATION_OVERRIDES.md)。

输入必须带有有效的运行指针，并来自可信客户端成员采集；输出必须与输入分开。补全会重新生成分类，但保留成员、应用类型、时长证据和原始采集时间，不代表重新核验当前所有权。审计记录 `operation=metadata_enrichment`、`parent_run` 和逐应用商店状态；`metadata.state=partial` 表示有应用未补全，旧元数据保留。`--appid` 只限制请求范围，输出仍包含整个原库。支持 `--cache-dir`、`--refresh-metadata`，沿用串行限速、缓存与有限重试。补全期间会锁定输入和输出，避免与采集同时更新同一目标；大库首次补全可能耗时较长。

每次采集先在 `.steam_library.runs/<run_id>/` 写入库、审计、快照、两个分类结果、CSV/Markdown、摘要与探测状态。全部校验并刷盘后，最后原子替换 `steam_library.current.json`。这个指针是整轮运行的提交点；写入中断不会让读取者混用新旧产物。旧运行保留，不自动清理。

`steam_library.json`、`.audit.json` 及 `--snapshot-out` 是兼容副本。副本导出失败会告警，已提交的完整运行仍可读取。两个 Python 分类入口优先读取对应 `.current.json` 指向的运行，并校验全部文件 SHA-256；未使用运行指针的外部工具不享有整轮一致性保证。`-o custom.json` 对应 `custom.current.json` 和 `.custom.runs/`。不要把 `.current.json` 当普通库输出路径。

自定义采集输出使用同名 `--input`，不再需要先导出根目录分类文件：

```bash
python steam_picker.py --serve --input steam_live_test.json
# 独立导出表格或五维 JSON 仍可使用：
python classify_games.py -i steam_live_test.json
python classify_steam_games.py -i steam_live_test.json
```

picker 每次请求都重新核验选定指针并从同一运行目录读取分类与摘要。页面显示时间、状态、脱敏账号与运行编号；刷新页面即可跟随新运行。没有默认运行指针时仍可兼容旧根目录分类，但明确显示 `legacy_unverified`。`--no-store` 缺少部分商店标签，分类质量需另外评估。

### 实时成员、候选与完整性

`GetClientAppList` 是一次性 RPC，当前协议没有 AppOverview 流式接口的 `full_update/update_complete`。工具检查完整 JSON、明确 apps 数组、唯一机器会话、client_info 中的机器和账号，连续读取两次相同 AppID 集合，并复核会话未切换。只有通过这些检查的响应才可决定本次成员。来源记录 `state`、`error_code` 与 `completeness`。

**两次一致是工程保护，并不能证明 Steam 服务端没有持续遗漏。** 审计明确保存 `protocol_completion_marker=false` 和 `semantic_completeness_proven=false`。相对同账号上次实时结果，成员移除比例超过 20% 时阻止发布；核实变化后可调整 `--max-unexplained-removal-ratio 0.5`，范围 0..1。账号不同则拒绝覆盖，使用独立 `-o` 路径。没有旧账号审计时会提示无法建立比较基线。

实时清单经过核验时，快照/API/许可中的额外 AppID 只进入差异审计，不扩大当前成员。客户端不可用时，优先使用账号匹配的历史快照，其次为 Web API，生成 **candidate**，默认另存 `steam_library.candidates.json` 及独立运行指针，保留当前库。即使是 API-only 或纯离线导入，也不冒充实时客户端集合。`--allow-candidates` 可显式把候选导出到指定路径。许可/PICS 不再自动扩大降级成员；仅有许可时默认只保存失败诊断，必须加 `--allow-candidate-membership` 才启用实验性候选并集。两项开关分别控制候选成员来源和导出路径。

`--strict` 要求实时客户端与所有启用的成员来源成功；来源降级不切换运行指针。商店元数据和可选时长来源不影响严格模式的成员成功判定。来源失败、解析错误和疑似部分响应分别保留可诊断状态；账号冲突始终终止。

### 字段证据与分类

| 来源 | 用途 |
|------|------|
| `client_library` | 当前在线客户端的成员、名称、类型 |
| `web_api` | `GetOwnedGames` 名称和时长；免费/未审核参数减少遗漏，不能保证库全集 |
| `licenses` | 账号/共享许可及 PICS 信息，范围包含 DLC、工具等 |
| `client_last_played_times` | 独立的可选客户端时长协议适配 |
| `license_file` | 带账号快照或 TXT，属于历史证据 |

类型优先级为客户端 > PICS > 商店/缓存 > 历史快照 > unknown。未知字符串或数值枚举映射为 `unknown`，原始类型保留在 `raw_app_types`，不从名称猜测类型。许可的 `own/shared/free/expiring/package_ids` 保留包级证据；`free_only`、`expiring_only`、`shared_only` 是筛选集合差分，区别于“也有免费/共享许可”。PICS 缺少包信息时标记 partial，不能成为完整许可来源。

时长逐字段采用 Web API > ClientGetLastPlayedTimes > 客户端旧格式字段 > 许可旧格式字段 > 快照。`playtime_evidence` 保留全部数值、时间、来源和冲突标记，不简单取最大值。`playtime.state` 为 `unknown`、`known_zero`、`known_nonzero`、`historical`。快照值保留为历史时长，不当作本轮实时值；历史值不计入 `playtime_known`。表格分别显示“未知”“0 分钟”“3 分钟”“1h 5m”或带“历史”前缀。

两个 Python 分类入口共用加载、运行校验与类型选择逻辑，保留各自原有分类体系：

```bash
python classify_games.py
python classify_steam_games.py
python classify_games.py --include-type game,demo
python classify_games.py --include-type all
# 候选库需要显式允许
python classify_games.py -i steam_library.candidates.json --allow-candidates --include-unknown
```

默认只分类明确的 game。旧的 `--include-demo`、`--include-non-game`、`--include-unknown` 仍可用，新增 `--include-unknown-type` 别名。`--include-type` 存在时使用该精确集合，优先于旧开关。原始记录保留未选类型。空结果仍由运行 manifest 绑定版本。

### 快照、其他模式与缓存

```bash
python steam_collect.py --source api --no-store
python steam_collect.py --owned-only --no-store
python steam_collect.py --source client --local-session --no-store
python steam_collect.py --local-session --no-store --snapshot-out library.snapshot.json
# 纯离线，不读取凭据或联网；默认另存候选结果
python steam_collect.py --apps-file library.snapshot.json --no-api --no-store
```

新快照保留 schema_version=2，增加 run_id、producer（Git 提交与 dirty 标记）、账号、生成时间、complete、completeness、record_count 和 apps_sha256。导入校验账号、条数及校验和；兼容旧 v2 快照和 UTF-8/UTF-16 BOM 的 `AppID 名称` 文本。TXT 无法核验账号与年龄。快照 `freshness` 保存年龄，24 小时以内记 fresh、之后 stale；只说明最近验证时间，不推断所有权失效。

商店元数据成功缓存 7 天，默认 `.steam_cache`。错误分别记录 not_found（6 小时）、access_denied（10 分钟）、rate_limited / parse_error（60 秒）、transient_error（30 秒），避免把短时网络问题长期缓存为下架。`--refresh-metadata` 强制更新，`--cache-dir` 改目录，`--no-store` 完全跳过。元数据失败不删除成员。

### 安全和适用边界

访问令牌留在 Node helper，带令牌的 Web 请求也在 helper 内完成；Python 接收白名单应用字段与稳定错误码。刷新凭据仅经私有管道进入 helper；扫码授权仍由 Python 写入认可的系统密钥环，本机会话不持久化。HTTP(S) 系统代理由 Python 检测后经私有管道交给 helper。日志不输出原始网络异常、Cookie 或访问令牌。

报告提到的 `CAppOverview` 不属于当前 ClientComm 响应，工具不会伪造字段或完成标记。运行目录的 `playtime_probe.json` 列出未解决 AppID 并记录 `APP_OVERVIEW_NOT_EXPOSED_BY_CLIENTCOMM`；这不是“已完成 AppOverview 真实补时长实验”。Windows QR 长期授权、macOS/Linux 密钥环、Steam Families 变化与退款场景仍需要相应真实环境验证，不能由单元测试代替。

审计包含按类型统计的集合差异、上次运行的增减、字段证据、来源状态与元数据缓存统计；所有 JSON 运行产物及非空记录携带 run_id，manifest 为整套文件提供哈希和版本绑定。

### 报告落地后的运行策略

```bash
# 日常：成员必须可信，辅助 API 失败也可发布带 degraded 状态的实时库
python steam_collect.py --local-session --no-store --strict-membership
# 指定某个辅助来源也必须成功
python steam_collect.py --local-session --no-store --strict-membership --require-source web_api
# 仅检查环境和依赖；不读取凭据、不探测网络
python steam_collect.py --diagnose
```

`--strict` 保留原语义：所有启用的成员相关来源必须健康；独立时长仍是可选来源。`--strict-membership` 只要求可信实时客户端清单。默认非严格模式下，API 失败不会删除客户端成员。临时 HTTP 错误最多请求 3 次，并在预算内遵守 Retry-After；认证错误和无效数据不盲目重试。Node 来源审计中的 attempts 是实际 HTTP 尝试次数，客户端核验本来就包含多个 RPC。

CLI 从认证/采集开始到检查与发布结束持有操作系统文件锁，第二个同目标进程报 `OUTPUT_BUSY`；进程崩溃后锁由操作系统释放。锁文件保留属于正常现象。该保证针对 CLI，直接调用 Python 发布函数的集成方仍应持有同一锁。

失败诊断写入 `.<output>.failed-runs/<run_id>/diagnostic.json`，不切换 current，且不写原始异常、token、Cookie、API Key。成功运行新增 `missing_from_web_api.json`，保留逐项许可证据，不猜测遗漏原因。`--diagnose` 与运行环境记录包含依赖版本，无法确认的 Steam 客户端版本仍为 null。

发布前按 `schemas/` 校验库、审计和新快照，并检查时长状态与值一致。库继续使用 v2 数组，旧字段保持兼容；CSV 增加 nullable 数值列 `playtime_minutes` 和 `playtime_status`，原 `playtime` 显示列保留。`categories` 缺失或损坏时多人/手柄为 null，明确空数组才为 false；旧缓存失效并按新语义重建。分类已修复 Action/Indie 宽泛类型误判和标签空格。

自动化使用现有 unittest 与 `npm test`，新增跨平台离线 CI 配置；没有把真实 Steam 认证或账号权益操作放入 CI。`requirements-tested.txt` 固定已验直接依赖版本，不声称锁定所有平台的传递依赖。新增 `python tools/check_secrets.py` 源码凭据模式扫描，但它不替代 Git 历史审计。参见 [RELEASE_NOTES.md](RELEASE_NOTES.md) 的迁移和待验证清单。

### 已验证结果（2026-09-12）

Windows 本机登录态、项目虚拟环境、HTTP(S) 代理下，`--local-session --no-store --strict` 真实采集通过：客户端 388 条（377 game、5 application、2 demo、4 beta），Web API 358 条，补回 30 条（27 game、2 demo、1 application）。361 条有明确时长，27 条仍未知。运行产物哈希、分类 AppID 集合与 run_id 已核验。报告落地版本 Python 63 项、Node 17 项回归测试通过。

这些数字是一个账号的实测样本，不是其他账号的预期数量，也不代表 `GetOwnedGames` 已能返回全集。已验证的是本次客户端补充采集链路；未知时长、协议层全集证明及上面列出的跨平台/账号变化场景仍未解决或未验证。

```bash
python -m unittest discover -s tests -v
node --test tests/test_steam_client.cjs tests/test_steam_web_sources.cjs
```

## 3. 自动分类并输出表格

```bash
python classify_games.py
```

- 输入：`steam_library.json`（由上一步生成）。
- 输出：
  - **game_library_classified.csv**：表格数据（Excel/脚本用）。
  - **game_library_classified.md**：Markdown 表格（文档用）。
- 分类体系：**主分类**（每款一个）+ **多标签**（可多个），规则在 `classify_games.py` 的 `MAIN_CATEGORY_RULES` 与 `TAG_RULES`。
- 维护规则说明：见 **CLASSIFICATION_RULES.md**。

## 4. 修改分类规则

- 编辑 `classify_games.py` 中的 `MAIN_CATEGORY_RULES`（主分类顺序与关键词）、`TAG_RULES`（标签条件/关键词）。
- 修改后重新运行 `classify_games.py` 即可更新 CSV/MD。
- 详细说明见 **CLASSIFICATION_RULES.md**。

---

## 5. 在本地「应用」分类（选游戏）

本工具默认在本地「选游戏」并用 Steam 启动；旧收藏写回脚本属于独立实验路径，尚未完成通用账号与持久性验收。

### 5.1 使用五维分类结果（steam_library_classified.json）

若你已用 `classify_steam_games.py` 生成了 `steam_library_classified.json`（核心玩法 / 细分流派 / 氛围 / 强度 / 一句话安利），可用 **steam_picker.py** 按这些维度筛选并用 Steam 打开游戏。

### 5.2 命令行用法

```bash
# 列出所有游戏（前 50 条）
python steam_picker.py

# 按维度筛选
python steam_picker.py --intensity 低              # 只想「电子榨菜」
python steam_picker.py --vibe 解压                 # 氛围：解压/治愈
python steam_picker.py --primary 策略 --intensity 高
python steam_picker.py --sub 肉鸽
python steam_picker.py --name 龙                   # 名称包含「龙」

# 用 Steam 启动筛选结果中的第 0 个游戏
python steam_picker.py --intensity 低 --open 0
```

参数简写：`-p` 核心玩法、`-s` 细分、`-v` 氛围、`-i` 强度、`-n` 名称、`-o` 打开第 N 个。

### 5.3 网页选游戏（推荐）

```bash
python steam_picker.py --serve
```

会启动只监听 `127.0.0.1` 的受限 HTTP 服务并自动打开浏览器，在页面里按「核心玩法 / 细分流派 / 氛围 / 强度」筛选，点击「在 Steam 中打开」即可启动对应游戏。关闭终端或 Ctrl+C 可停止服务。只允许 `/`、`/index.html`、`/api/library`、`/api/run`，不提供目录列表、账号配置、Git 或快照文件。`--port` 可更改端口，`--no-browser` 可禁止自动打开浏览器。

### 5.4 其他用法

- 把 `steam_library_classified.json` 导入 **Playnite**、**GOG Galaxy** 等支持自定义标签的启动器，可在那里打标签、分组。
- 将分类结果导出为 CSV/表格，在 Notion、Excel 里做「今日玩啥」清单。

---

## 6. 写回 Steam 收藏夹（可选）

如果你希望把 `steam_collections_result.json` 的分类写回 Steam 收藏夹，可以用 `import_script.js`。

1. **完全退出 Steam**（含托盘图标）。
2. 安装依赖：
   ```bash
   npm install
   ```
3. 显式设置目标账号的 32 位 AccountID，再执行导入（不要填写 SteamID64）：
   ```powershell
   $env:STEAM_ID_32 = "你的32位AccountID"
   node import_script.js
   ```

说明：
- 脚本会优先写入 LevelDB，若未检测到收藏命名空间，会自动改用 `cloud-storage-namespace-1.json` 并生成 `.bak` 备份。
- 导入完成后，启动 Steam，在「库」→「收藏夹」中核对分类与数量。
- 未配置或配置无效时，脚本在写入前退出。此旧收藏路径仍待独立持久化验收；采集、补全和 picker 无需执行此步骤。
