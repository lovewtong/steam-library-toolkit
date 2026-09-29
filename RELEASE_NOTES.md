# v1.0.0 发布说明

首个稳定版本面向 **Windows、本机、单个明确账号**，提供采集、审计、元数据补全、分类校正、本地浏览和收藏计划导出。发布目标及检查约定见 [R5 发布准备](R5_RELEASE_PREPARATION.md)；正式发布时间和提交以 GitHub Release/标签为准。

## 本版本交付

- 客户端核验后的清单决定本轮成员；API、许可与快照保留各自证据，未知时长不会变成零，候选数据不冒充当前拥有。
- 完整运行保存账号、来源、字段观察和哈希；先发布完整产物再原子切换 current，失败、取消及异常缩减保护旧有效数据。
- 商店补全有缓存、1–4 有限并发、共享间隔、总请求预算、取消和有限重试；保留 missing/empty/invalid 及字段应用动作。
- 28 条 AppID 校正规则、31 项固定复核样本和逐字段依据；人工校正可离线重建，picker 展示已核验运行及分类依据。
- 收藏入口默认预览；显式导出绑定账号及运行的计划。**旧 Python `--write` 已停用**；计划不是 Steam 写回文件。

## 安装与已测环境

Windows 真人链路使用 Python **3.14.2**、Node **22.19.0**；三平台离线 CI 使用 Python **3.12**、Node **22**。旧最低声明 Python 3.10+/Node 18+ 没有完整验收证据。Linux/macOS 暂只有离线测试证据，QR 路径也不等同于本次 Windows 本机会话验收。

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-tested.txt
npm ci
.\.venv\Scripts\python.exe -m pip check
```

`requirements-tested.txt` 固定直接依赖，并非跨平台全部传递依赖锁；Node 使用提交的 package-lock.json。完整检查为 129 Python/24 Node，实际最终提交的 CI 结果须在发布记录中核对。

## 迁移与六项流程

先备份现有个人配置、`classification_overrides.local.json` 和完整输出目录；已核验运行需要 **current 指针与其引用的隐藏 `.runs` 目录一同保留**，仅复制平面库 JSON 不够。不要编辑旧运行里的文件。不同账号使用独立目录，新版本首次运行使用新输出名，便于保留旧版本结果。

以下在项目根目录执行；先将 `$steamAccount` 改为目标账号的 17 位 SteamID64。示例输出放到 Git 忽略的 `outputs` 下，仅在本地保存。

```powershell
$steamAccount = 'YOUR_STEAMID64'
.\.venv\Scripts\python.exe steam_collect.py --local-session --account $steamAccount --no-store --strict-membership -o outputs/v1/library.json
.\.venv\Scripts\python.exe steam_enrich.py --input outputs/v1/library.json -o outputs/v1/enriched.json
# 按 CLASSIFICATION_OVERRIDES.md 编辑 classification_overrides.local.json 后重建
.\.venv\Scripts\python.exe steam_reclassify.py --input outputs/v1/enriched.json -o outputs/v1/reclassified.json
.\.venv\Scripts\python.exe steam_picker.py --serve --input outputs/v1/reclassified.json
# 在另一终端预览或导出计划
.\.venv\Scripts\python.exe steam_sync_collections.py --input outputs/v1/reclassified.json --account $steamAccount --dry-run
.\.venv\Scripts\python.exe steam_sync_collections.py --input outputs/v1/reclassified.json --account $steamAccount --export-only -o outputs/v1/collections.local.json
```

采集同时生成审计和分类：以相应 `.current.json` 指向的完整运行查看 `steam_library.audit.json`、`summary.json`、`classified.json`、`classified.csv` 等。`--strict-membership` 要求客户端成员可信；需要所有启用来源都成功时改用 `--strict`。本次导出不重新核验当前所有权，计划的 `ownership_revalidated` 和 `write_supported` 均为 false。

兼容性变化：缓存使用 v5，旧版本会按需重新抓取；CSV 新增最近游玩状态/来源/观察时间列，读取方应按列名解析；个人校正按 AppID 整条替换内置规则。旧平面分类不能作为收藏计划输入；`--from-result`、`--use-api` 被拒绝，`--no-backup` 已移除。不要把新计划传给 `import_script.js`、`steam_sync_leveldb.js` 或 npm 的旧 sync-leveldb 命令，这些工具不在首发支持流程内。

## 已知限制

游戏库绝对完整性未证明；27 条未知时长仅是验收账号样本，不能填零或当作所有账号固定数量。31 个分类样本通过不等于全库准确率；名称启发式及氛围/强度等推断仍可能错误，未确认项保持未知并支持人工校正。

R2 的 388 项冷缓存 582.236 秒、暖缓存中位 0.843 秒只描述指定环境，不保证所有网络/规模性能。多账号/多设备、Families、退款/撤销/免费周末变化、跨系统真人认证、自动收藏写回和旧 Node 写回工具尚未完成验收。哈希用于完整性检查，不是数字签名。源码凭据模式检查不等同于 Git 历史或全面安全审计。

证据见 [R1](R1_CLASSIFICATION_REVIEW.md)、[R2](R2_PERFORMANCE_BASELINE.md)、[R3](R3_WINDOWS_ACCEPTANCE.md)、[R4](R4_FINAL_REVIEW.md)。下方保留早期记录，其版本、计数和“待验证”状态属于当时，不覆盖本节的首发范围。

---

# 历史记录：报告落地、采集契约与 picker 修复

基线为 `a28e4de`。修复分支已推送至 PR #2；第一阶段验收、全库补全与分类覆盖结果见 [PHASE_ONE_ACCEPTANCE.md](PHASE_ONE_ACCEPTANCE.md)，合并状态以 GitHub 为准。

## 行为变化

- 可信客户端集合继续决定当前成员。没有实时客户端时，历史快照优先、Web API 次之；许可不再自动扩大降级集合。显式 `--allow-candidate-membership` 可恢复实验性候选并集，`--allow-candidates` 单独控制候选输出路径。
- 新增 `--strict-membership`、`--require-source` 和仅环境检查的 `--diagnose`。现有 `--strict`、`--local-session`、`--login`、`--owned-only` 等保留。
- 临时 HTTP 失败有限重试，遵守预算内的 Retry-After；账号、认证和结构异常不盲目重试。API 失败且客户端可信时，默认模式继续，严格模式按所选策略处理。
- CLI 从采集开始到发布结束持有 OS 文件锁，第二个同目标进程直接报告 OUTPUT_BUSY。正常退出或崩溃都释放锁；锁文件有意保留。兼容输出路径也纳入锁范围。
- 失败诊断写入独立 failed-runs，既不覆盖 current，也不序列化原始异常和凭据。
- 发布前执行本地 JSON Schema、快照条数/校验和、跨文件运行标识与时长状态校验。成功运行增加逐条 API 差异文件和环境/依赖版本信息。
- CSV 保留旧 `playtime` 显示列，新增 nullable `playtime_minutes`、`playtime_status`。库保持 v2 数组格式，没有机械迁移为报告示例的新顶层对象。
- 商店缺失/损坏 categories 时多人与手柄能力为 null；明确空数组才是 false。旧缓存版本失效，避免继续使用被错误归零的能力字段。
- 修复 Action 被当射击、Indie 被当休闲的宽泛规则，以及 KNOWN 标签空格；`--include-type game, demo` 支持空格。
- picker 通过 `--input` 读取校验后的运行，并在同一 API 响应中返回分类和版本。刷新页面跟随指针，无需根目录分类副本。旧默认无指针时兼容旧分类并明确标记未核验。
- picker 只监听回环地址，仅开放四条 GET/HEAD 路由，阻止项目目录/配置/Git/快照访问；修复重复 serve_forever，支持 --port、--no-browser。批处理优先使用 `.venv`。

## 快速使用

```powershell
python -m pip install -r requirements-tested.txt
npm ci
python steam_collect.py --local-session --no-store --strict-membership -o steam_live_test.json
python steam_picker.py --serve --input steam_live_test.json
```

已经使用项目 `.venv` 时，将 `python` 替换为 `.\.venv\Scripts\python.exe`。刷新页面会重新读取同一采集目标的最新运行，不会在不同账号/不同输出文件之间自动挑选“最新”。

## 验证与发布准备

```powershell
python -m unittest discover -s tests -p "test_*.py"
npm test
python tools/check_secrets.py
git diff --check
```

Windows/Linux/macOS 离线 CI 已运行通过，不访问真实 Steam 账号。`requirements-tested.txt` 固定已验的直接依赖；不冒充跨平台完整传递依赖锁。

源码模式扫描不扫描 Git 历史、不替代全面 secrets scanner。第一阶段另行检查了可达历史并复核命中项；旧收藏脚本的固定账号已改为显式配置，但公开历史没有重写。本阶段已推送修复分支，没有导入真实 Steam 收藏。

## 已验证与待验证

- 本次合成集成 fixture 保留 388/358/377/361/27 的集合关系，名称和账号为测试值。这是回归形状，不是账号未来固定数量，也不是新在线证据。
- 真实 Windows 本机会话、当前 HTTP(S) 代理下，报告落地版本重新采集严格模式成功：388 条成员、377 game、358 API、361 已知时长、27 未知。
- 第一阶段回归为 63 项 Python、17 项 Node 测试通过；独立 clone 与全新虚拟环境也已通过。全库补全 388 条，376 条详情成功、12 条未取得，耗时约 13 分钟；输出仍为 388 条成员、377 game，原库及成员/类型/时长证据保持不变。
- 账号许可 owner_account_ids 只在实际许可证据有数值时保留；不根据游戏名字/免费属性或数量差推断缺失原因。
- 仍保留原来的客户端类型优先和 Web API 时长优先策略。报告示例中的不同优先级不是足以推翻当前实测契约的新证据，冲突值继续进入审计。
- 独立补全命令 `steam_enrich.py` 已加入：读取已核验运行、使用独立输出，保留成员/类型/时长和采集时间；可按 AppID 补全，失败保留旧元数据并逐条记录。2026-09-13 增加 `--workers 1–4`、共享请求间隔、字段状态/覆盖率，以及类别 ID 支持能力判断；缓存 v4 会按需重新获取旧缓存。详见 [METADATA_ENRICHMENT.md](METADATA_ENRICHMENT.md)。完整 auth 统一别名、自动扫码回退仍是后续产品设计。
- 家庭共享前后、退款/撤销/免费周末、跨平台长期 QR、同名机器、多账号真实切换和绝对完整性协议仍待相应真实环境验收。没有为测试改变账号权益。
- 27 条未知时长仍未恢复。不能填 0，`semantic_completeness_proven` 仍为 false。
- 收藏写回路径仍需独立治理，本次不进行账号/收藏写操作。

## 后续真人验收清单

第二阶段已增加协议字段类型采样、真实进程中断/刷盘失败/万级库测试，并修复非有限令牌时间校验及历史时长摘要。当前本地回归为 69 项 Python、20 项 Node；真人场景的完成范围见 [PHASE_TWO_VALIDATION.md](PHASE_TWO_VALIDATION.md)，不能将模拟测试视为跨环境真人验收。

- [ ] 现有合法家庭环境的 self/shared 对照与 owner evidence。
- [ ] 自然发生的退款/撤销前后快照，旧快照不复活移除成员。
- [ ] 免费周末到期前后客户端、许可、API 对照。
- [ ] 多机同名、多账号 A→B→A，独立输出与串号拒绝。
- [ ] macOS Keychain、Linux Secret Service/KWallet 的扫码、重启读取、失效与清理。
- [ ] Steam 更新后重新跑协议 fixture 与本机 smoke。
- [ ] 更大库与慢网络测试；在有证据时研究新的时长或同步完成通道。
