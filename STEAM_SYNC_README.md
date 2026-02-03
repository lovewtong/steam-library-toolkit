# 路线 B：API + 本地文件写入（写回 Steam 收藏）

把分类结果写回 Steam 客户端保存收藏的文件，使库内出现对应收藏分组。

**收藏来源二选一：**

- **`steam_collections_result.json`**（推荐）：由 `node classify_steam.js` 生成，格式为「分类名 → [appid]」。使用 `--from-result` 时读此文件。
- **`steam_library_classified.json`**：由 `classify_steam_games.py` 生成，按强度/核心玩法/细分/氛围多维度。不加 `--from-result` 时读此文件。

---

## 自动化导入收藏（用 steam_collections_result.json）

若你已有 `steam_collections_result.json`（由 `node classify_steam.js` 生成），可**半自动**写回 Steam 收藏：

1. **完全关闭 Steam**（含托盘图标）。
2. 在项目目录执行：
   ```bash
   python steam_sync_collections.py --from-result --write
   ```
3. 重新启动 Steam，在库中查看是否出现对应收藏。

**注意**：Steam 可能用 LevelDB 存收藏，你机器上的 `cloud-storage-namespace-1.json` 有时会被覆盖或不被读取，导致写回后库内仍只有旧收藏或「未分类」。若出现这种情况，请改用「手动按 steam_collections_guide.md 建收藏」或本地工具（如 `steam_picker.py --serve`）按分类浏览。详见下文「若写回后 Steam 不认」。

---

## 前提

1. **Steam 必须关闭**：读写 `cloud-storage-namespace-1.json` 时若 Steam 在运行，可能冲突或损坏，脚本会检测并提示。
2. **路径**：收藏文件位于  
   `Steam/userdata/{你的 Steam64_ID}/config/cloudstorage/cloud-storage-namespace-1.json`  
   （Stelicas 等项目采用同一路径；部分老客户端可能仍用 LevelDB，本脚本针对 JSON 文件。）
3. **配置**：`config_local.json` 中需有 `steam_id`（Steam64 位）；可选 `steam_install_path`（不填则尝试注册表/环境变量 `STEAM_PATH`）；写回前建议先 `--dry-run`。

---

## 步骤 1：用 Web API 或本地库拿到拥有游戏

- **不传 `--use-api`**：脚本用本地 `steam_library.json` 里的 appid 作为「拥有游戏」，只把库里已有的游戏归入收藏。
- **传 `--use-api`**：用 Steam Web API `IPlayerService/GetOwnedGames` 拉取拥有游戏（需在 `config_local.json` 填 `steam_api_key`）。  
  API Key 申请：<https://steamcommunity.com/dev/apikey>  
  **注意**：不要用已废弃的 `ISteamApps/GetAppList` 做全量 app 列表；用 `GetOwnedGames` + appid 匹配即可。

---

## 步骤 2：分类规则（你已有）

脚本直接使用 `steam_library_classified.json`：  
按「强度 / 核心玩法 / 细分 / 氛围」四个维度，每个维度值生成一个收藏（如 `强度-低`、`核心玩法-策略/模拟`），收藏内容为对应 appid 列表。  
只包含「拥有游戏」列表里的 appid（来自 API 或 `steam_library.json`）。

---

## 步骤 3：写回 Steam（关键）

1. **只导出、不写 Steam 目录**（安全）  
   ```bash
   python steam_sync_collections.py --from-result --export-only
   ```  
   会从 `steam_collections_result.json` 生成 `steam_collections_export.json`（收藏名 -> [appid]），可手动合并或自用。  
   若不用 `--from-result`，则从 `steam_library_classified.json` 生成。

2. **试跑：不写文件**  
   ```bash
   python steam_sync_collections.py --from-result --dry-run
   ```  
   会打印 Steam 路径、目标 JSON 路径、将生成的收藏数量与名称，**不读写任何文件**。

3. **实际写回（请先关闭 Steam）**  
   ```bash
   python steam_sync_collections.py --from-result --write
   ```  
   - 默认会先备份原文件为 `cloud-storage-namespace-1.json.bak`（可用 `--no-backup` 关闭）。  
   - 脚本会尝试解析现有 JSON 格式（列表 / 单 key 命名空间 / 键值对等），在原有结构上**追加**本脚本生成的收藏；若无法识别格式则**不覆盖**原文件，只提示你用手动合并 `steam_collections_export.json`。

4. **用 API 拉取拥有游戏再写回**  
   ```bash
   python steam_sync_collections.py --use-api --write
   ```  
   先通过 GetOwnedGames 拿到拥有游戏，再按分类写回。

---

## 可选配置

| 来源 | 项 | 说明 |
|------|-----|------|
| config_local.json | steam_id | Steam64 位 ID（必须） |
| config_local.json | steam_api_key | 仅在使用 --use-api 时需要 |
| config_local.json | steam_install_path | Steam 安装目录（可不填，自动检测） |
| 环境变量 | STEAM_PATH | 同 steam_install_path |
| 环境变量 | STEAM_ID | 同 steam_id |

---

## 若写回后 Steam 不认

- 不同 Steam 版本/分支可能使用不同格式（如 LevelDB 与 JSON）。若你机器上实际不是 `cloud-storage-namespace-1.json`，脚本会跳过写入并提示。
- 可先用 `--export-only` 得到 `steam_collections_export.json`，再按 Stelicas 或官方文档说明，手动合并到当前客户端使用的存储中。
- 写回后请**完全退出并重新打开 Steam** 再查看库内收藏是否生效。

### 若脚本显示写入成功但库内仍只有旧收藏，或只剩「未分类」

可能原因：

1. **Steam 实际用 LevelDB 存收藏**  
   Steam 官方/第三方工具（如 DumpSteamCollections）说明：收藏数据主要在 **LevelDB** 里，`cloud-storage-namespace-1.json` 可能是同步/缓存用。直接改 JSON 不一定被客户端采用，甚至可能被覆盖或解析失败，导致界面回退成「只剩未分类」。
2. **云同步或校验覆盖**  
   启动时 Steam 用服务器或本地 LevelDB 覆盖了我们写过的 JSON，导致写回的内容消失；若格式不被认可，也可能被当成无效数据，只显示「未分类」。

**建议：**

- **先恢复原有收藏**：若你还有备份，把  
  `userdata/886001714/config/cloudstorage/cloud-storage-namespace-1.json.bak`  
  重命名回 `cloud-storage-namespace-1.json`，完全关闭 Steam 后替换回去，再启动 Steam，看「收藏夹」「策略游戏」等是否恢复。
- **不再依赖写回 JSON**：为避免再次出现「只剩未分类」，建议**不要再用 `--write` 写回该文件**。改用本地工具按分类浏览和启动游戏：
  - 用 **`steam_picker.py --serve`** 打开网页，按「核心玩法 / 强度 / 氛围」等筛选并启动；
  - 或查看 **`steam_collections_guide.md`** 按分类清单在 Steam 里**手动**建收藏（一次性的活，但稳定可控）。

若仍想尝试写回，请务必先备份，并在写回前完全关闭 Steam；写回后先离线模式启动查看。但鉴于当前表现，写回方式风险较高，不推荐作为主方案。
