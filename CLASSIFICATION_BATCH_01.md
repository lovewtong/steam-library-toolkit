# 分类复核批次 01

2026-09-29，基于 main `036819641b99ee390d3c60d39a30e6085524cbd8` 的主类差异清单，选择 6 个原版 AppID，新增共享校正规则。表格和 picker 的主类由相同 AppID 规则决定，本地化名称不会改变已确认结果。内置规则由 28 条增至 34 条。

## 编辑结论与依据

全部通过 Steam 公开 appdetails 返回的 `steam_appid`、`name`、`type=game` 与开发商商店正文核对原版身份。页面年龄提示或浏览工具访问失败时，读取相同 AppID 的公开 API 正文；没有登录、读取令牌或使用玩家标签作为人工确认依据。

| AppID / 游戏 | 旧表格主类 → 新主类 | 确认的细分类型 | 第一方依据与项目取舍 |
|---|---|---|---|
| 7670 / BioShock | RPG → 射击 | 武器/异能射击 | [原版商店正文](https://store.steampowered.com/api/appdetails?appids=7670&l=english) 明确射击、武器和基因异能；按主要战斗方式粗分，不否认 RPG 元素。 |
| 8850 / BioShock 2 | 动作/冒险 → 射击 | 武器/异能射击 | [原版商店正文](https://store.steampowered.com/api/appdetails?appids=8850&l=english) 单人介绍说明射击及武器、Plasmids 双持。 |
| 8870 / BioShock Infinite | 动作/冒险 → 射击 | 武器/异能射击 | [原版商店正文](https://store.steampowered.com/api/appdetails?appids=8870&l=english) 描述武器、Vigors 和裂隙辅助战斗；以主要战斗方式选主类。 |
| 63380 / Sniper Elite V2 | 动作/冒险 → 射击 | 狙击潜行 | [原版商店正文](https://store.steampowered.com/api/appdetails?appids=63380&l=english) 描述狙击、弹道与隐蔽追踪；[原版手册](https://cdn.steamstatic.com/steam/apps/63380/manuals/Sniper%20Elite%20V2%20Manual%20E%20STEAM.pdf?t=1601483610) 对应相同 AppID。未使用重制版资料替代原版身份。 |
| 214550 / Eets Munchies | 策略 → 休闲/益智 | 物理解谜 | [Klei 玩法介绍](https://support.klei.com/hc/en-us/articles/360029880071-What-is-Eets-Munchies) 及[原版商店正文](https://store.steampowered.com/api/appdetails?appids=214550&l=english) 明确物理解谜；采用核心谜题玩法，覆盖泛 Strategy 标签优先级。 |
| 241260 / Sherlock Holmes: Crimes and Punishments | 动作/冒险 → 休闲/益智 | 侦探推理 | [原版商店正文](https://store.steampowered.com/api/appdetails?appids=241260&l=english) 描述调查、审问和演绎；项目采用解谜展示组，不否认其 Adventure 类型。 |

上述主类是项目的编辑选择，不声称唯一正确的官方分类。只把主类与细分类型标为 `reviewed`；氛围、强度及推荐语继续保留各自推断、未知或生成状态。BioShock 三作细分从“叙事FPS”改为更直接对应所读正文的“武器/异能射击”，推荐语依既有失效规则重新生成。

本批将这 6 个 AppID 的主类决策迁移到共享规则，但保留名称启发式作为其他 AppID 及未确认细项的既有推断，避免删除系列名称规则影响未复核作品。相同名称出现在另一 AppID 上时，不获得人工确认状态。未开展系列其他版本、所有细项或全库人工验收。

## 可重放验证

新增独立样本 `tests/fixtures/classification-batch-01.json`，冻结公开身份、genres、修改前结果、编辑预期、依据和审核日期。原 R1 的 31 项样本文件不变，仍为 25 项刷新证据、4 项历史证据、2 项未知；新批次 6 项全部读取了第一方正文，不能合并成“37 项全部新核实”。

```powershell
.\.venv\Scripts\python.exe tools/review_classification_sample.py
.\.venv\Scripts\python.exe tools/review_classification_sample.py --sample-set batch-01
.\.venv\Scripts\python.exe -m unittest discover -s tests -p 'test_classification*.py'
```

注册的所有样本集合共同覆盖每条内置规则。回归检查全部 34 条规则的改名/冲突名称输入、逐字段审核范围，以及新批次在不可变运行、picker 和收藏计划中的一致性。新增 3 项回归；本地完整 144 Python（37.430 秒）和 24 Node 通过。远端精确提交 CI 以对应 PR 为准。

已对本机保存的 R5 库进行离线候选重建，连接被阻断：388 条原始记录除 run_id 外完全不变，377 条 game、27 条未知时长不变。仅这 6 个 AppID 的表格/五维分类记录改变；其余记录不变，旧指针和旧运行文件哈希不变，表格、picker、收藏计划核对通过。

| 主类队列指标 | 修改前 | 修改后 |
|---|---:|---:|
| 待复核 | 349 | 343 |
| 主类差异 | 128 | 122 |
| 主类来自名称推断 | 243 | 237 |
| 主类未知 | 2 | 2 |

原因可以重叠。6 项退出主类队列不表示所有细项均已复核，差异数量也不等于错误数量或全库准确率。完整个人产物与公开 API 响应只留本机；仓库仅保存有限公开样本和聚合说明。

## 应用及后续

已有运行不会自动改变。更新规则后，按 [人工校正说明](CLASSIFICATION_OVERRIDES.md) 离线重建到独立输出，再让 picker 和计划导出读取新目标；本地同 AppID 规则仍整体覆盖内置规则。

下一批继续核对有限 P1 样本，证据不足者保留未知；不要批量接受名称推断。此批不改变采集来源、元数据补全、Steam 收藏写回能力，也不移动或公开绑定 `209e60b` 的 v1.0.0 草稿。后续正式发布若包含本批，应另行选择目标并复核受影响的验收。
