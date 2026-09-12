# 游戏库分类维护规则

## 数据来源与流程

1. **采集**：Windows 已登录 Steam 时运行 `python steam_collect.py --local-session --no-store --strict`，核验客户端清单，并结合 Web API、许可与游玩记录生成库和来源审计。其他授权方式见 [README.md](README.md)。
   - `config_local.json` 为可选本地配置，不提交；无需为客户端授权配置 API Key。带账号的采集/审计产物也应留在本地。
2. **分类**：运行 `python classify_games.py`，优先加载 `steam_library.current.json` 指向的库并校验整轮产物，做主分类 + 多标签，输出：
   - `game_library_classified.csv`：表格数据，便于 Excel/脚本处理。
   - `game_library_classified.md`：Markdown 表格，便于文档展示。
   - 本文件：分类体系与维护规则说明。

默认只分类明确的 `game`，两个 Python 分类入口共用类型筛选逻辑。需要 Demo 时使用 `--include-type game,demo`。客户端不可用时采集默认另存候选库，分类候选需显式 `--allow-candidates`。自定义采集输出需通过 `-i` 指定，例如 `python classify_games.py -i steam_live_test.json`；不指定会读取默认库。

## 分类体系

- **主分类**：每款游戏仅一个，用于粗分（如 射击、动作/冒险、RPG、策略、模拟经营、休闲/益智、体育/竞速、独立/其他、其他）。
- **标签**：可多个，用于细粒度描述（如 单人、多人、合作、手柄、剧情、Roguelike、开放世界、像素/复古、恐怖、回合制、卡牌 等）。

## 如何修改分类结果

1. **改规则**：编辑 `classify_games.py` 中的 `MAIN_CATEGORY_RULES` 与 `TAG_RULES`。
   - **主分类**：按列表顺序匹配，第一个命中的即为主分类；可调整顺序或增删「类型(genres)」「关键词(keywords)」。
   - **标签**：每条规则独立，满足即打上对应标签；支持 `condition`（如 multiplayer/controller/coop/single）或 `keywords`。
2. **改数据做实验**：存在运行指针时，直接修改平铺 `steam_library.json` 不会改变分类输入；修改运行目录中的文件则会导致哈希校验失败。请将库复制为独立文件（如 `library_manual.local.json`），确保旁边没有同名 `.current.json`，通过 `python classify_games.py -i library_manual.local.json` 单独测试。它属于人工编辑的实验输入，不再是已核验的采集结果；不要覆盖原运行目录。正式调整分类时优先修改规则并重新生成。
3. **手动覆盖**：若需固定某游戏的主分类，可在 `classify_games.py` 中为指定 `appid` 做特例映射，或维护一张「主分类覆盖表」JSON/CSV，在分类脚本中读取并合并到结果。

## 规则定义位置

| 内容     | 位置 |
|----------|------|
| 主分类规则 | `classify_games.py` → `MAIN_CATEGORY_RULES` |
| 标签规则   | `classify_games.py` → `TAG_RULES` |

## 输出字段说明

- **game_library_classified.csv / .md** 包含：游戏名、appid、总时长、最近游玩日期、主分类、标签（多标签用分号/顿号分隔）、是否多人、是否手柄支持；CSV 的 `run_id` 列与 Markdown 中的运行编号标记用于追溯采集版本。
- 总时长优先使用 Web API，其次为独立客户端时长来源，历史快照仅作历史证据。未知、明确 0 分钟、正时长和历史值分别显示，不把缺失时长当作 0；最近游玩来自 `rtime_last_played`（若有）。多人/手柄由商店数据推断，`--no-store` 采集可能缺少这些元数据。字段来源与冲突详情见采集审计和 `playtime_evidence`。

CSV 新增数值列 `playtime_minutes`（未知为空）及 `playtime_status`（unknown/known/historical），原 `playtime` 继续用于人读。`--include-type game, demo` 与 `game,demo` 等价。Action 不再直接代表射击，Indie 不再直接代表休闲；KNOWN 标签在生成时去除首尾空格。
