# Steam 游戏库「AI 智能分类」进度与差距

## 终极目标

**通过 AI 智能对 Steam 游戏库进行分类**：自动为每款游戏打上「核心玩法 / 细分流派 / 氛围 / 强度 / 一句话安利」等标签，并能在本地按分类选游戏、启动。

---

## 已完成内容

| 模块 | 说明 |
|------|------|
| **游戏库采集** | `steam_collect.py`：Steam API 拉取拥有游戏 + 可选商店 API 补充类型/标签 → `steam_library.json` |
| **规则+已知列表分类** | `classify_steam_games.py`：基于 **KNOWN 手写字典**（约 200+ 款）+ **关键词/类型规则**，生成五维分类 → `steam_library_classified.json` |
| **本地按分类使用** | `steam_picker.py`：命令行按维度筛选、`--serve` 网页选游戏、`steam://rungameid/` 启动；`run_steam_picker.bat` 一键打开选游戏页 |
| **导出清单** | `steam_picker.py --export-collections` → `steam_collections_guide.md`（按分类分组的游戏清单，可手动在 Steam 里建收藏） |
| **写回 Steam 尝试** | `steam_sync_collections.py`：写 `cloud-storage-namespace-1.json`（已证明易被覆盖/解析失败，**不推荐**，见 STEAM_SYNC_README.md） |
| **文档与流程** | `README.md`（采集→分类→选游戏）、`STEAM_SYNC_README.md`、`STEAM_COLLECTIONS.md`、`CLASSIFICATION_RULES.md` |

**当前分类方式**：**无 AI**。完全依赖  
1）手写 KNOWN 表（精准匹配游戏名）；  
2）`steam_library.json` 里的 `genres` 等字段做关键词规则推断。  
未在 KNOWN 里、且规则覆盖不到的游戏，会得到较泛的默认值（如「多种元素」「风格各异」「中」等）。

---

## 距离「AI 智能分类」还差什么

要实现**真正的 AI 智能分类**，需要补上以下能力：

### 1. 接入大模型（核心缺口）

- **做什么**：对「未在 KNOWN 中、或希望由 AI 重新标注」的游戏，调用 LLM API（如 OpenAI / Claude / 本地模型），根据**游戏名、商店简介、类型标签**等，生成五维：`primary / sub / vibe / intensity / slogan`。
- **输入**：可从 `steam_library.json` 提供 `name`、`appid`、`genres`、`categories`；若采集时拉过商店详情，还可提供 `short_description` 等，提高 AI 准确度。
- **输出**：与现有 `steam_library_classified.json` 单条结构一致，便于直接合并或覆盖。

### 2. 成本与策略

- **按需调用**：只对「未命中 KNOWN、且未命中规则」或「用户指定要重标」的游戏调 AI，减少 token 消耗。
- **结果缓存**：AI 结果写回 KNOWN 或单独缓存文件（如 `steam_ai_classified_cache.json`），下次同款游戏不再请求 API。
- **批量与限速**：大批量时需限速、重试、断点续跑，避免 API 限流或中途失败全丢。

### 3. 与现有流程衔接

- **流程**：`steam_library.json` → 先跑 `classify_steam_games.py`（KNOWN + 规则）→ 对「未分类/低置信」项调用 AI → 合并进 `steam_library_classified.json`。
- **可选**：新增脚本 `classify_steam_games_ai.py` 或给 `classify_steam_games.py` 加 `--ai` 参数，读配置（如 `config_local.json` 里的 `openai_api_key` 或 `anthropic_api_key`），只对未覆盖游戏调 AI 并写回。

### 4. 可选：人机协作

- 用户在 picker 网页或命令行里对某条游戏的分类做修正；修正结果写回 KNOWN 或缓存，下次优先使用，减少重复 AI 调用并越用越准。

### 5. 可选：更丰富输入

- 若当前 `steam_library.json` 没有商店简介，可在采集阶段（`steam_collect.py`）增加对商店 `short_description` 的拉取；或对接 IGDB 等游戏数据库 API，为 AI 提供更多上下文。

---

## 小结

| 状态 | 内容 |
|------|------|
| **已完成** | 游戏库采集、规则+已知列表分类、本地按分类选游戏/启动、导出清单、写回 Steam 尝试（不推荐）、完整文档与一键流程。 |
| **未完成（与「AI 智能分类」的差距）** | 接入 LLM API 对游戏做五维标注；只对未覆盖游戏调用、结果缓存与增量更新；与现有 classify 流程衔接；可选的人机修正与更丰富输入。 |

补上「接入大模型 + 缓存 + 与现有脚本衔接」后，即可在不大改现有流程的前提下，实现**通过 AI 智能对 Steam 游戏库进行分类**的终极目标。
