# Steam 游戏库本地采集与自动分类

English: `README_EN.md`

## 如何实现自动分类（推荐流程）

不写 Steam 内部文件、不依赖写回收藏，用本地脚本完成「自动分类 + 按分类选游戏」：

| 步骤 | 命令 | 说明 |
|------|------|------|
| 1. 有游戏库数据 | `python steam_collect.py` 或已有 `steam_library.json` | 若已有 `steam_library.json` 可跳过 |
| 2. 自动分类 | `python classify_steam_games.py` | 生成 `steam_library_classified.json`（五维分类） |
| 3. 按分类用 | `python steam_picker.py --serve` | 浏览器里按 核心玩法/强度/氛围 筛选，点「在 Steam 中打开」启动 |

**一键打开选游戏页（分类已生成时）：**

```bash
cd /path/to/steam-collections
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
pip install -r requirements.txt
npm ci
```

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

输出保留原有顶层 JSON 数组格式，默认文件为 `steam_library.json`，来源审计为 `steam_library.audit.json`。使用 `-o 路径` 时默认审计文件为同名 `.audit.json`。原始记录包含应用类型，**两个 Python 分类入口默认只分类明确的 `game`**：

```bash
python classify_games.py
python classify_steam_games.py
# 需要时显式纳入 Demo、其他已知类型或未知类型
python classify_games.py --include-demo
python classify_games.py --include-non-game --include-unknown
```

旧 JSON 或 TXT 清单可能没有 `app_type`，使用 `--include-unknown` 纳入分类，或重新采集补充类型。未知类型仍保留在原始 JSON；未知时长显示“未知”，不会伪装为 `0h`。

### 数据来源及边界

| 来源 | 用途与限制 |
|------|------------|
| `web_api` | `GetOwnedGames` 提供名称、时长、最近游玩；默认启用免费游戏/免费许可并关闭未审核过滤，仍可能漏项 |
| `client_library` | `IClientCommService` 查询所选在线桌面客户端；成功后，以这次清单决定输出成员 |
| `licenses` | `steam-user` 的客户端许可及 PICS 产品信息，用于类型、账号/共享许可标识和差异核对；含 DLC、工具等，不能直接当作游戏库 |
| `license_file` | 带账号的 JSON 快照或旧 TXT 导入；属于历史记录，不代表实时持有 |

客户端游玩记录还通过 `Player.ClientGetLastPlayedTimes` 尝试补齐 API 缺失时长。这是独立的实验性协议适配：失败不会阻断成员采集，审计记录 `client_playtime_status`，未返回的数据保留 `null`。Web API 时长优先。

实时客户端成功时，旧快照、API 和许可中额外的 AppID 只进入审计差异，不会把当前清单中已移除的应用重新加入。客户端不可用时，改用成功来源的并集并明确标记 `degraded`；许可候选可能包含客户端未显示的应用。`--strict` 要求实时客户端及所有启用的成员来源成功，否则不更新输出；它不要求商店详情或实验性时长补充成功。所有来源失败、账号冲突或输入损坏也不会覆盖原库文件。每个 JSON 文件使用原子替换，多个输出文件不构成整体事务。

**`status=ok` 表示启用来源成功，不能证明所有 Steam 账号或未来版本都绝对完整。** 桌面筛选、共享许可、免费应用及个人资料计数口径可以不同。客户端必须在线；第三方客户端协议也可能随 Steam 更新改变。

商店元数据成功结果缓存 7 天，默认目录 `.steam_cache`，可用 `--cache-dir` 改位置、`--refresh-metadata` 强制更新。首次请求每款间隔约 1.5 秒。商店失败或下架应用不会导致成员被丢弃；`--no-store` 完全跳过该步骤。

### 其他模式与快照

```bash
# 仅 Web API；--owned-only 恢复传统 API 过滤
python steam_collect.py --source api --no-store
python steam_collect.py --owned-only --no-store
# 仅客户端与许可，不调用 GetOwnedGames
python steam_collect.py --source client --local-session --no-store
# 导出绑定账号、生成时间和类型的客户端快照
python steam_collect.py --local-session --no-store --snapshot-out library.snapshot.json
# 离线重建：不读认证配置、不联网；快照时长不当作新采集时长
python steam_collect.py --apps-file library.snapshot.json --no-api --no-store
```

JSON 快照结构为 `{"schema_version":2,"steam_id":"17位ID","generated_at":"带时区ISO时间","apps":[{"appid":10,"name":"名称","app_type":"game"}]}`。采集与快照账号必须一致。没有实时客户端时，快照结果明确降级。

兼容旧清单：每行 `AppID 名称`，例如 `570 Dota 2`；支持 UTF-8、UTF-8 BOM、UTF-16 BOM。TXT 没有账号和生成时间，导入会提示无法核验。它只应来自你确认过账号的许可导出；包含登录提示、错误文本或为空时拒绝导入。`--apps-file` 不能和 `--owned-only` 同用。纯 API/TXT 且 `--no-store` 的记录可能没有类型，分类需 `--include-unknown`。

### 输出字段

| 字段 | 说明 |
|------|------|
| `appid`, `name`, `app_type` | 应用 ID、名称、类型；未知类型保留为 `unknown` |
| `playtime_minutes`, `playtime_2weeks_minutes` | 分钟；无法取得时为 `null`，有依据的零为 `0` |
| `playtime_available` | 总时长是否有可用来源 |
| `last_played_at`, `last_played_iso` | 最近游玩 Unix/UTC 时间，未知为 `null` |
| `sources`, `provenance` | 条目来源以及名称、类型、时间等字段来源 |
| `membership_source`, `membership_status` | 当前客户端观察值或完整性未经确认的候选 |
| `ownership` | 许可报告的 `account_license`、`shared`，没有证据时 `unknown` |
| `genres`, `categories`, `is_multiplayer`, `is_controller` | 可选商店信息；不可用时为 `[]` / `null` |

审计包含账号、时间、来源状态、类型统计、已知时长数量，以及客户端/API/快照/许可之间的 AppID 差异；不包含访问令牌。授权通过子进程私有管道传递，不写入命令参数或采集输出。扫码登录只更新系统凭据存储，`--local-session` 不持久化令牌。

回归测试（无需 Steam 账号）：

```bash
python -m unittest discover -s tests -v
node --test tests/test_steam_client.cjs
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
