# Steam 游戏库本地采集与自动分类

English: [README_EN.md](README_EN.md)

## 如何实现自动分类（推荐流程）

不写 Steam 内部文件、不依赖写回收藏，用本地脚本完成「自动分类 + 按分类选游戏」：

| 步骤 | 命令 | 说明 |
|------|------|------|
| 1. 有游戏库数据 | `python steam_collect.py --local-session --no-store --strict` | Windows 已登录 Steam；其他授权方式见安装说明 |
| 2. 自动分类 | `python classify_steam_games.py` | 生成 `steam_library_classified.json`（五维分类） |
| 3. 按分类用 | `python steam_picker.py --serve` | 浏览器里按 核心玩法/强度/氛围 筛选，点「在 Steam 中打开」启动 |

**一键打开选游戏页（分类已生成时）：**

```bash
cd /path/to/steam-library-toolkit
python steam_picker.py --serve
```

**若刚更新了游戏库，先重新分类再打开选游戏页：**

```bash
python classify_steam_games.py && python steam_picker.py --serve
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

每次采集先在 `.steam_library.runs/<run_id>/` 写入库、审计、快照、两个分类结果、CSV/Markdown、摘要与探测状态。全部校验并刷盘后，最后原子替换 `steam_library.current.json`。这个指针是整轮运行的提交点；写入中断不会让读取者混用新旧产物。旧运行保留，不自动清理。

`steam_library.json`、`.audit.json` 及 `--snapshot-out` 是兼容副本。副本导出失败会告警，已提交的完整运行仍可读取。两个 Python 分类入口优先读取对应 `.current.json` 指向的运行，并校验全部文件 SHA-256；未使用运行指针的外部工具不享有整轮一致性保证。`-o custom.json` 对应 `custom.current.json` 和 `.custom.runs/`。不要把 `.current.json` 当普通库输出路径。

使用自定义输出名后，分类时也必须指定同一输入，否则会读取默认的旧库。例如本地测试输出为 `steam_live_test.json`：

```bash
python classify_games.py -i steam_live_test.json
python classify_steam_games.py -i steam_live_test.json
python steam_picker.py --serve
```

采集生成的分类保存在本轮运行目录；上面的分类命令将结果导出到默认 CSV/Markdown 和 `steam_library_classified.json`，供现有 picker 使用。picker 当前读取这个平铺分类文件，不会自动跟随采集运行指针。`--no-store` 可验证库成员与时长，但会缺少部分商店标签，规则分类的细致程度会受影响。

### 实时成员、候选与完整性

`GetClientAppList` 是一次性 RPC，当前协议没有 AppOverview 流式接口的 `full_update/update_complete`。工具检查完整 JSON、明确 apps 数组、唯一机器会话、client_info 中的机器和账号，连续读取两次相同 AppID 集合，并复核会话未切换。只有通过这些检查的响应才可决定本次成员。来源记录 `state`、`error_code` 与 `completeness`。

**两次一致是工程保护，并不能证明 Steam 服务端没有持续遗漏。** 审计明确保存 `protocol_completion_marker=false` 和 `semantic_completeness_proven=false`。相对同账号上次实时结果，成员移除比例超过 20% 时阻止发布；核实变化后可调整 `--max-unexplained-removal-ratio 0.5`，范围 0..1。账号不同则拒绝覆盖，使用独立 `-o` 路径。没有旧账号审计时会提示无法建立比较基线。

实时清单经过核验时，快照/API/许可中的额外 AppID 只进入差异审计，不扩大当前成员。客户端不可用时，成功来源的并集是 **candidate**，默认另存 `steam_library.candidates.json` 及独立运行指针，保留当前库。即使是 API-only 或纯离线导入，也不冒充实时客户端集合。`--allow-candidates` 可显式把候选导出到指定路径。

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

### 已验证结果（2026-09-12）

Windows 本机登录态、项目虚拟环境、HTTP(S) 代理下，`--local-session --no-store --strict` 真实采集通过：客户端 388 条（377 game、5 application、2 demo、4 beta），Web API 358 条，补回 30 条（27 game、2 demo、1 application）。361 条有明确时长，27 条仍未知。运行产物哈希、分类 AppID 集合与 run_id 已核验。Python 42 项、Node 15 项回归测试通过。

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

Steam 客户端**不支持**把自定义分类写回 Steam 服务器，但你可以用分类数据在本地「选游戏」并用 Steam 启动。

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

会启动本目录的简单 HTTP 服务并自动打开浏览器，在页面里按「核心玩法 / 细分流派 / 氛围 / 强度」筛选，点击「在 Steam 中打开」即可启动对应游戏。关闭终端或 Ctrl+C 可停止服务。

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
3. 执行导入：
   ```bash
   node import_script.js
   ```

说明：
- 脚本会优先写入 LevelDB，若未检测到收藏命名空间，会自动改用 `cloud-storage-namespace-1.json` 并生成 `.bak` 备份。
- 导入完成后，启动 Steam，在「库」→「收藏夹」中核对分类与数量。
