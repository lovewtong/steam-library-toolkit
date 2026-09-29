# R3 Windows 干净环境与六项端到端验收

2026-09-29，在干净提交 `a4095be6d6a1ba3d80d29f55f50324db3539e9ec` 的独立 clone 中完成 R3。采集、审计、补全、分类校正、本地浏览和收藏计划导出均通过。本轮没有修改生产代码，也没有合并或发布版本；R4 最终候选复审和 R5 整合发布仍待执行。

## 环境与证据边界

- 新建独立 clone 和 Python 虚拟环境，没有复制原项目的个人配置、原虚拟环境或 node_modules。初始不存在 config_local.json、.env、classification_overrides.local.json。
- Windows，Python 3.14.2、Node 22.19.0；安装 requirements-tested.txt 和 npm ci，pip check 通过。直接依赖为 requests 2.34.2、keyring 25.7.0、vdf 3.4、jsonschema 4.26.0；完整 pip freeze 保存本机。
- “干净”指项目配置与安装环境隔离，不是全新操作系统、全新 Steam 账号或禁用包下载缓存。复用已安装的系统运行时和已登录 Steam，包管理器可以使用下载缓存。Node 安装仍有旧 LevelDB 依赖弃用提示，本轮没有做依赖升级。
- pip 在沙箱内两次持续无输出，中断后用受控安装完成，固定版本未改变；不能把这个环境限制当作项目依赖安装必然失败。
- 用户已授权本机会话测试。显式选择此前授权的同一账号，项目通过 Windows DPAPI 读取本机凭据并经私有子进程管道使用；令牌没有写入验收文件。使用已配置的本机 HTTP 代理，没有执行新的扫码登录或持久凭据保存。
- 全部生产运行均记录上述 SHA 且 dirty=false。临时人工校正属于显式本地输入，保存在该轮不可变规则产物中，不能只凭 dirty=false 忽略它；验收结束已撤销。

## 六项链路结果

| 能力 | 实际验证 | 结果 |
|---|---|---|
| 采集 | 新环境 --local-session --no-store --strict，显式绑定账号 | 状态 ok；388 条记录，377 game、5 application、2 demo、4 beta；361 条已知时长、27 条未知时长 |
| 来源与审计 | 核对客户端成员、许可、游玩记录、Web API、同轮产物及账号 | client_library complete 388、licenses complete 2434、client_last_played_times complete 204、web_api complete 358；成员来源为 client_snapshot |
| 补全 | 新采集库全库补全，再对固定 8 项强制刷新商店 | 全库复用有效缓存 388 命中，382 success / 6 not_found；8 项刷新零缓存命中，7 success / 1 not_found；均为 partial |
| 分类校正 | 临时 AppID 规则→离线重建→核对表格/picker→撤销规则并再重建 | 显式主类/子类生效，旧氛围与强度失效为待核对，依据可见；撤销后原分类逐项恢复，原始库字段不变 |
| 本地浏览 | 实际浏览器访问回环服务，名称与主类组合筛选，刷新查看新运行，展开依据 | 初始 377 项；名称筛选 2 项，组合筛选 1 项；校正与撤销后刷新均读取对应新 run_id，标签文本按普通文字显示 |
| 收藏计划 | 真实 CLI dry-run、export-only、错误账号和旧 --write 拒绝 | dry-run 文件集合与哈希不变；导出 377 个 game、359 个收藏分组；账号、运行和成员一致；write_supported=false、ownership_revalidated=false |

补全明确复制 R2 的有效缓存到 R3 独立目录，而不是宣称再次执行全库冷缓存；R2 原缓存未变。固定刷新子样本与 R2 一致。R2 已负责完整冷/暖性能测量，R3 验证这批新采集数据经过实际补全、发布与下游功能的衔接。

这批新库在 --no-store 后四个元数据字段均未知；补全后 genres/categories 各 376 项非空、12 项空或未知，多人 true/false/unknown 为 128/248/12，手柄为 251/125/12。请求成功并不等于字段完整，缺失值保留规则继续生效。

临时分类规则明确标为“R3 临时功能验收，不得作为真实游戏分类”，刻意改变主类并加入 `<b>` 字面文本，用于检查失效规则、展示与转义。它没有修改内置分类或用户原项目配置，测试后按文件哈希确认并移除；最终收藏计划来自恢复后的运行。

## 保护检查与补充场景

- 全部源与输出 manifest 文件哈希通过；补全前后只允许四个元数据字段、对应 provenance.store_metadata 和 run_id 改变。成员、顺序、名称、应用类型、时长及证据、其他 provenance、原采集时间与来源保持。
- 分类重建前后原始库除 run_id 外完全一致；snapshot 除新 run_id/producer 外保持。每阶段 SHA、run_id、指针及文件摘要都有本地检查点。
- HTTP `/api/library` 与已核验产物完全一致，`/api/run` 与同轮摘要一致。非允许路由返回 404，错误 Host 和跨源 Origin 返回 403。服务绑定 127.0.0.1。
- 使用独立虚拟账号快照执行真实离线 CLI：降级结果另存 candidates；picker 默认拒绝，显式 --allow-candidates 才允许查看；strict-membership 失败不切换已有有效指针。
- 错误账号导出和旧 --write 均失败，已导出的计划哈希不变。确认空集合、损坏/跨轮产物、中断与原子替换失败等隔离回归包含在完整测试中，见 tests/test_collection_plan.py、tests/test_phase_two.py、tests/test_steam_runs.py 和 HTTP 相关测试。
- 干净环境完整 **129 项 Python（36.778 秒）、24 项 Node** 通过，源码凭据模式扫描通过。模式扫描不是对所有历史对象或任意秘密形式的绝对保证。
- 浏览器检查了 Steam URI 与对应 AppID；未点击启动游戏，未写入 Steam 收藏。临时浏览页和服务均已关闭。

## 本地证据与复现入口

个人证据保存在本机 `outputs/r3-acceptance`：environment.json、collection-check.json、enrichment-check.json、correction-check.json、restore-check.json、plan-check.json、api-check.json、failure-check.json 及汇总 acceptance.json。该目录还包含独立 clone、逐阶段不可变运行、计划和测试驱动脚本；完整账号、拥有清单与逐游戏时长不随本报告公开。

主要 CLI 顺序如下。账号、路径及规则必须使用验收者自己的有效输入；原库输出保持独立。补全可指定显式缓存目录，人工校正规则按项目校正格式保存到本地文件，重建前后分别核对再撤销测试规则。

```powershell
.\.venv\Scripts\python.exe steam_collect.py --local-session --no-store --strict --account STEAMID64 -o collected.json
.\.venv\Scripts\python.exe steam_enrich.py --input collected.json -o enriched.json --cache-dir CACHE_DIR --workers 2
.\.venv\Scripts\python.exe steam_reclassify.py --input enriched.json -o view.json
.\.venv\Scripts\python.exe steam_picker.py --input view.json --list
.\.venv\Scripts\python.exe steam_picker.py --input view.json --serve --no-browser
.\.venv\Scripts\python.exe steam_sync_collections.py --input view.json --account STEAMID64 --dry-run
.\.venv\Scripts\python.exe steam_sync_collections.py --input view.json --account STEAMID64 --export-only -o collections-plan.json
```

R3 只证明该 Windows 单账号环境下约定流程通过。未知时长、未取得的元数据、绝对成员完整性、多账号/Families/自然权益变化、其他系统真人认证、实际游戏启动及自动收藏写回不因此变成已验收。若 R4/R5 改动相关生产行为，应重新评估并补跑受影响链路。
