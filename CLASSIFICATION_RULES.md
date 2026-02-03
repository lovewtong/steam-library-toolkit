# 游戏库分类维护规则

## 数据来源与流程

1. **采集**：运行 `steam_collect.py`，从 Steam 获取游戏库并写入 `steam_library.json`。  
   - API Key / Steam ID 仅存于本地 `config_local.json`（已加入 `.gitignore`），**不要提交到仓库**。
2. **分类**：运行 `classify_games.py`，基于 `steam_library.json` 做主分类 + 多标签，输出：
   - `game_library_classified.csv`：表格数据，便于 Excel/脚本处理。
   - `game_library_classified.md`：Markdown 表格，便于文档展示。
   - 本文件：分类体系与维护规则说明。

## 分类体系

- **主分类**：每款游戏仅一个，用于粗分（如 射击、动作/冒险、RPG、策略、模拟经营、休闲/益智、体育/竞速、独立/其他、其他）。
- **标签**：可多个，用于细粒度描述（如 单人、多人、合作、手柄、剧情、Roguelike、开放世界、像素/复古、恐怖、回合制、卡牌 等）。

## 如何修改分类结果

1. **改规则**：编辑 `classify_games.py` 中的 `MAIN_CATEGORY_RULES` 与 `TAG_RULES`。
   - **主分类**：按列表顺序匹配，第一个命中的即为主分类；可调整顺序或增删「类型(genres)」「关键词(keywords)」。
   - **标签**：每条规则独立，满足即打上对应标签；支持 `condition`（如 multiplayer/controller/coop/single）或 `keywords`。
2. **改数据**：直接修改 `steam_library.json` 后重新运行 `classify_games.py`，会覆盖输出的 CSV/MD。
3. **手动覆盖**：若需固定某游戏的主分类，可在 `classify_games.py` 中为指定 `appid` 做特例映射，或维护一张「主分类覆盖表」JSON/CSV，在分类脚本中读取并合并到结果。

## 规则定义位置

| 内容     | 位置 |
|----------|------|
| 主分类规则 | `classify_games.py` → `MAIN_CATEGORY_RULES` |
| 标签规则   | `classify_games.py` → `TAG_RULES` |

## 输出字段说明

- **game_library_classified.csv / .md** 包含：游戏名、appid、总时长、最近游玩日期、主分类、标签（多标签用分号/顿号分隔）、是否多人、是否手柄支持。
- 总时长来自 Steam 的 `playtime_forever`（分钟），最近游玩来自 `rtime_last_played`（若有）；多人/手柄由商店页 `categories` 推断。
