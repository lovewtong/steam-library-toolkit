# 通过 LevelDB 自动写入 Steam 收藏

**状态（2026-09-28）：下文保留为旧实验工具说明，尚未完成账号安全、写入保护和持久化验收，不作为推荐操作流程。** Python 收藏入口已改为[校验后预览/导出计划](STEAM_SYNC_README.md)，新计划不能直接交给本工具；F10 验收不覆盖此 Node 工具。

JSON 写入未生效本身不能证明客户端使用了哪一种存储格式。下面描述的是旧脚本尝试直接写 LevelDB 的路径，不能保证当前 Steam 版本接受或保留这些写入。

---

## 前提

1. **Steam 必须完全关闭**（含托盘图标），否则 LevelDB 被占用，脚本会报错或无法写入。
2. **路径**：LevelDB 在  
   `{Steam安装目录}\config\htmlcache\Local Storage\leveldb`  
   不是 userdata 下的 cloudstorage。脚本会从 `config_local.json` 读 `steam_install_path` 和 `steam_id`。
3. **依赖**：需先安装 Node 依赖  
   `npm install`  
   会安装 `classic-level`（用于读写 LevelDB）。

---

## 步骤

1. **完全关闭 Steam**（含托盘）。
2. 在项目目录执行：
   ```bash
   node steam_sync_leveldb.js
   ```
   或：
   ```bash
   npm run sync-leveldb
   ```
3. 看到「已写入 LevelDB」后，**启动 Steam**，在库中查看是否出现 26 个收藏。

---

## 试跑（不写库）

不关 Steam 也可以先试跑，只打印将要写入的收藏，不打开 LevelDB、不写入：

```bash
node steam_sync_leveldb.js --dry-run
# 或
npm run sync-leveldb:dry
```

---

## 若提示「LevelDB 目录不存在」

脚本会依次尝试这些路径（Windows 可能与 Linux 不同）：

- `{Steam}\config\htmlcache\Local Storage\leveldb`
- `{Steam}\config\Htmlcache\Local Storage\leveldb`
- `{Steam}\config\HTML Cache\Local Storage\leveldb`
- `{Steam}\userdata\{你的ID}\config\htmlcache\Local Storage\leveldb`

若都不存在，请按下面检查：

1. **确认 Steam 安装路径**  
   `config_local.json` 里的 `steam_install_path` 必须是实际安装目录（例如 `C:\Program Files (x86)\Steam` 或 `C:\Program Files (x86)\Software\Steam`）。脚本会打印「你的 Steam config 目录下现有文件夹」，用来核对路径是否正确。

2. **先让 Steam 建好目录**  
   LevelDB 常在首次使用新库界面后才创建。请：**启动 Steam → 进入「库」→ 完全退出 Steam**，再运行一次 `node steam_sync_leveldb.js`。

3. **若仍没有 htmlcache**  
   部分 Steam 版本或安装方式可能不用该目录。若脚本列出 config 下没有 `htmlcache`，则你当前环境可能不支持通过 LevelDB 写入收藏，只能改用手动建收藏或 `steam_picker.py --serve`。

---

## 若写入后库内仍只有「未分类」

可能原因：

- Steam 版本/分支不同，key 或格式有变化，脚本当前只按公开的 DumpSteamCollections 格式处理。
- 云同步或其它机制覆盖了本地 LevelDB。

此时只能改用手动建收藏，或继续用 `steam_picker.py --serve` 等本地工具按分类浏览。

---

## 数据来源

脚本从 **`steam_collections_result.json`** 读取「分类名 → [appid]」（由 `node classify_steam.js` 生成），把这些收藏**追加**到 LevelDB 里现有数据中，不会删掉你原有收藏。
