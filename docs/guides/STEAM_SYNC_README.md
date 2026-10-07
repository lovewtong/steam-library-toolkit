# 收藏计划：校验、预览与导出

`steam_sync_collections.py` 现在只生成收藏计划。旧 `--write` 写入 Steam 存储的功能已停用；此前按猜测格式追加 JSON、仅告警后继续写入的实现已移除。

## 使用方式

先选择已有采集运行及对应的 SteamID64。`--input` 接受输出名或 `.current.json` 指针；必须有完整运行，不能只提供平面 JSON。

```powershell
python steam_sync_collections.py --input steam_library.json --account YOUR_STEAMID64 --dry-run
python steam_sync_collections.py --input steam_library.json --account YOUR_STEAMID64 --export-only -o collection_plan.local.json
```

将 `YOUR_STEAMID64` 替换为目标账号的 17 位 SteamID64。这些命令只读取本地运行，不读取凭据、不连接 Steam，也不要求退出客户端。

- 默认仅预览；只有显式 `--export-only` 才保存计划。
- `--dry-run` 读取并校验输入，不创建或替换计划、备份、锁文件或输出目录；同时指定 `--export-only`、`--write` 时仍只预览。这里指应用数据，Python 自身可能维护导入缓存；需要抑制字节码缓存可用 `python -B`。
- 单独使用 `--write` 返回 `COLLECTION_WRITE_DISABLED`，不会导出或写 Steam。
- `--from-result`、`--use-api` 返回 `COLLECTION_LEGACY_SOURCE_DISABLED`。无账号绑定的分类映射或 GetOwnedGames 列表不再作为入口的数据依据。
- `--no-backup` 已移除，因为此入口没有 Steam 写回功能。

## 校验与空集合

导出前检查运行 manifest 全部文件哈希、库与审计结构、显式账号、运行编号、客户端成员证据及分类成员集合。要求成功且完整的已核验客户端清单，拒绝候选集合、可疑缩减状态、跨账号和混合运行。

分类 AppID 必须与该运行中的 `game` 类型成员完全一致；application、demo、beta 等不会自动加入。缺少或多出分类成员都失败。每个游戏按强度、核心玩法、细分、氛围生成分组；空标签显示“未分类”。这些分组沿用分类结果，不代表逐游戏人工确认。

确认的空客户端库生成 `eligible_appids: []`、`collections: {}`，不会回退到全部分类。兼容数据函数中 `None` 表示没有过滤条件，`[]` 表示没有成员；它们不再参与 CLI 的来源回退。

## 计划内容与输出保护

输出是 `kind: steam_collection_plan` 的 JSON 对象，包含：

| 字段 | 含义 |
|---|---|
| `steam_id`、`run_id` | 所选账号和来源运行 |
| `source_manifest_sha256` | 本次读取的运行指针摘要 |
| `membership_observed_at` | 原客户端成员观察时间 |
| `membership_count`、`eligible_appids` | 原库数量及允许参与分类的 game AppID |
| `collections` | 收藏名到 AppID 数组的映射 |
| `ownership_revalidated: false` | 本次未联网重新确认当前所有权 |
| `write_supported: false` | 本计划不是可执行的 Steam 写回操作 |

快照即使通过哈希和来源校验，也可能已经过时。导出不会让历史成员变成当前所有权证明。哈希用于发现产物变化，不是数字签名或防篡改认证。

不允许覆盖来源指针、对应库、运行目录、配置或旧分类输入；已有目标必须是同账号的计划。导出前再次检查指针，变化则失败。计划通过临时文件和原子替换保存，替换失败保留旧计划。这不是多个导出进程之间的事务锁。

计划含账号和游戏清单，应保存在本地；示例的 `*.local.json` 被 Git 忽略。它不兼容旧的“收藏名 → AppID 数组”顶层格式，**不能直接交给 `import_script.js` 或 `steam_sync_leveldb.js`**。

## 验收边界及后续

F10 对此 Python 入口通过修复空集合、只读预览、绑定运行校验和停用旧写回来处理。`tests/test_collection_plan.py` 使用隔离合成运行验证这些约束以及失败后的文件保护；没有进行真实认证或 Steam 存储写入。

独立 Node 写回工具没有在本轮修改或完成安全、持久化验收，不是绕过停用限制的推荐替代入口。当前可用本地 picker 浏览，或按计划在 Steam 中人工建立收藏。

恢复自动写回前，需要另行确认当前客户端的存储格式、目标账号与目录对应关系、写入前的新鲜成员核验、客户端停止条件、现有收藏保留、幂等性、备份恢复及重启/云同步后的持久性，并先在隔离副本验证。
