# 首次观察时间

首次观察时间用于回答“这款游戏最早在我保留的采集记录中何时出现”。它不是购买日期，也不是首次游玩日期。

## 记录方式

新采集会为可信客户端清单中的应用保存 `first_seen_at` 和 `first_seen_evidence`。日期采用来源的观察时间，统一为 UTC，不使用文件修改时间或商店发行日期。

同一账号、同一输出路径的后续采集会继承历史，包括已移除应用的记录；游戏重新出现时保留原日期。历史与库一起保存在运行审计中，只有整轮成功发布才生效。补全、重新分类保留原日期，不重新开始计时。

需要改用新输出路径时，显式指定同账号的旧完整运行：

```powershell
.\.venv\Scripts\python.exe steam_collect.py --local-session --no-store --strict-membership --history-from outputs/library.json -o outputs/next.json
```

旧运行没有该字段时，只能用其已核验客户端快照的观察时间作为历史起点，状态为 `historical`；不能还原更早的购买日期。没有有效观察时间、只有平面文件或候选清单时保持未知。工具只使用指定历史和当前输出的已保存账本，不自动扫描其他目录。

## 筛选和分组

页面可选择首次观察年份和月份，与玩法、名称、厂商条件取交集；年份列表单独提供“未知”。年月均按 UTC，跨时区的月末记录会先换算。

```powershell
.\.venv\Scripts\python.exe steam_picker.py --input outputs/next.json --first-seen-year 2026 --first-seen-month 10 --list
.\.venv\Scripts\python.exe steam_sync_collections.py --input outputs/next.json --account YOUR_STEAMID64 --group-by first_seen_year first_seen_month --dry-run
```

`first_seen_month` 分组使用完整 `YYYY-MM`，不同年份的同一月份不会混在一起。`--first-seen-year unknown` 只选未知日期；与月份同时使用时没有匹配结果。筛选为空不会回退到全库。表格 JSON、CSV、Markdown、页面和收藏计划采用同一日期。

## 许可时间推定：研究结果

当前安装的 `steam-user` 通过 `CMsgClientLicenseList.License` 提供 package 级 `time_created`，同时有 `owner_id`、`flags`、`license_type`、`payment_method` 等字段。上游文档也用 `time_created` 筛选取得超过一年的许可，见 [steam-user ownershipFilter](https://github.com/DoctorMcKay/node-steam-user#ownershipfilter)。这些字段尚未用来生成购买日期。

可以进一步保存“package 许可时间”的原始观察，再通过 PICS 的 package→AppID 映射生成推定。但需分别处理：

- 一个 package 对应多个应用，一个应用又可能有多个 package。
- 家庭共享可能关联其他所有者的许可，不能当成当前账号的购买。
- 免费许可、临时权益、激活码、组合包和许可重新取得都不等同于商店购买事件。
- 字段缺失或零值保持未知；不能用最早 package 日期自动替代应用的准确入库时间。

后续建议保留 package、所有者、来源和观察时间；只把已确认的自有永久许可日期标为推定值，并允许冲突和未知。要验证准确购买日期，还需要用户可核对的购买或激活记录。本批只实现首次观察，不加入许可日期推定字段。

## 验证记录（2026-10-05）

功能提交 `83e6183` 的三平台 CI 通过。回归覆盖重复采集、移除后重新出现、UTC 月界、同账号历史继承、跨账号拒绝、候选日期未知、补全与重分类保留日期，以及发布失败不提交账本。

在该干净提交上真实采集了 388 条记录，其中 377 个 game；从旧完整运行继承的日期均为 `historical`，落在 2026-09。表格、picker 和收藏计划日期一致。实际页面筛选 2026 年 9 月为 377 款，10 月和未知日期均为 0，恢复 9 月后为 377 款。

这验证了可用历史继承和筛选，没有验证实际购买日期，也没有发生真实新增、退款或离开家庭事件。真实家庭库另发现两款遗漏，见[账号场景记录](REAL_SCENARIO_VALIDATION.md)；首次观察时间只覆盖实际采集到的成员。

另在干净文档提交 `582b5d2` 上验证了厂商与时间组合：复制既有缓存到独立目录补全，382 次命中、6 项 `not_found`，不视为冷缓存性能基准。成员、类型、时长、首次观察及其历史账本保持，原指针和原缓存未变。表格、picker 与计划一致；页面 `2K + 2026-09` 为 13 款，再加入 `2K Australia` 为 4，切到 10 月为 0，恢复 9 月为 4。
