# Retired experiments / 旧实验工具

These Node scripts are retained for historical reference. They are outside the supported collection-plan workflow and have not passed current account, persistence and write-safety acceptance. See the [current plan guide](../docs/guides/STEAM_SYNC_README.md) and [historical LevelDB notes](../docs/history/STEAM_LEVELDB_SYNC.md).

这些 Node 脚本保留供历史研究，不属于正式收藏计划流程，尚未通过当前账号、持久化和写入保护验收。新导出的计划不能直接交给它们。

| Script / 脚本 | Earlier purpose / 早期用途 |
|---|---|
| `classify_steam.js` | Classify flat JSON by name heuristics / 对平面 JSON 按名称启发式分类 |
| `import_script.js` | Attempt direct collection storage writes / 尝试直接写收藏存储 |
| `steam_sync_leveldb.js` | Attempt direct LevelDB writes / 尝试直接写 LevelDB |

The npm shortcuts now use the `legacy:` prefix. The old `classify` and `sync-leveldb` shortcuts have been removed. Configuration and result files still resolve at the repository root; moving the scripts does not migrate any account data.

npm 入口改为 `legacy:` 前缀，原 `classify`、`sync-leveldb` 入口已移除。配置和结果文件仍从仓库根目录读取；移动脚本不会迁移账号数据。
