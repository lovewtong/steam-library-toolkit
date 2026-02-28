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
config_local.json (本地密钥，不提交)
        ↓
  steam_collect.py  →  steam_library.json
        ↓
  classify_steam_games.py →  steam_library_classified.json（五维分类）
        ↓
  steam_picker.py --serve  →  浏览器按分类选游戏、用 Steam 启动

（可选）classify_games.py →  game_library_classified.csv / .md
```

## 1. 本地配置（密钥不提交）

1. 复制 `config_local.example.json` 为 `config_local.json`。
2. 在 `config_local.json` 中填写：
   - **steam_api_key**：在 [Steam Web API Key](https://steamcommunity.com/dev/apikey) 申请。
   - **steam_id**：你的 64 位 Steam ID（可从个人资料页或第三方工具获取）。
3. `config_local.json` 已在 `.gitignore` 中，**切勿提交到仓库**。

## 2. 采集游戏库

```bash
pip install -r requirements.txt
python steam_collect.py
```

- **默认**：会请求 Steam 商店 API，为每款游戏补充类型、是否多人、是否手柄等，写入 `steam_library.json`。耗时较长（每款约 1.5 秒）。
- **默认会包含已游玩免费游戏/免费许可记录**。
- **仅要基础字段**（名称、appid、总时长、最近游玩）：  
  `python steam_collect.py --no-store`，速度快，不写可选字段。
- **只拉传统拥有游戏**（不含免费/非库存计数记录）：  
  `python steam_collect.py --owned-only`

输出 JSON 字段：

| 字段 | 说明 |
|------|------|
| appid, name | 游戏 ID、名称 |
| playtime_minutes | 总时长（分钟） |
| playtime_2weeks_minutes | 近两周时长（分钟） |
| last_played_at / last_played_iso | 最近游玩时间（Unix/ISO，可能为空） |
| genres, categories | 类型、商店分类（可选） |
| is_multiplayer, is_controller | 是否多人、是否手柄（可选） |

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
