# R4 最终候选复审与回归

日期：2026-09-29。审查对象：`273ac3f7b8c7f0cc80be42d8dda00a2998d3abe7`，分支 `fix/classification-quality-evidence`；开始检查时工作区干净。结论：**在首发六项能力及已声明的 Windows 单账号边界内，未发现新的发布阻塞项，可进入 R5 主线整合与发布准备。**本次为维护会话内的源码复核及验证，不是独立第三方批准，也不表示已经合并或发布。

## 复核范围与判断

以远端 main `cd31fa611ca572517b155d830f4ffc69a996595d` 到候选的差异为范围，结合现有整改记录，重点检查实际调用路径及失败保护。

| 路径 | 本次核查重点与结果 |
|---|---|
| 采集与来源 | 客户端成员、API、许可、快照仍分开表达；不可比较时不生成确定缺失结论，空库与来源不可用不混淆；时间 null 契约保留 |
| HTTP 传输 | 父进程总预算、取消、worker 回收及响应体上限；内存响应已消费，503/429 重试前关闭安全；长冷却共享 gate，不把延期写成失败缓存 |
| 元数据 | missing/empty/invalid、字段应用动作和观察/读取时间进入审计；类型补齐采用实际 store_api/store_cache 来源；补全保留成员及原采集证据 |
| 发布与重建 | 校验账号、schema、run_id、成员集合、manifest 哈希，先写完整运行再切 current；异常及疑似大幅移除保留旧指针；重建不调用认证或网络 |
| 分类与浏览 | AppID 校正优先、主类变更重置未指定细项，子类变更重建推荐语；逐字段区分 reviewed/inferred/unknown/generated；picker 固定一轮读取并转义文本，限制回环 Host/Origin 和公开路由 |
| 收藏计划 | 只读预览、dry-run、空集合、账号/运行/哈希/成员一致性、输出冲突及原子替换保护；旧 Python 写回继续拒绝，计划明确未重新核验当前所有权 |

没有发现需要修改生产代码的新问题。本次交付仅更新验收说明及本地任务记录；未读取 Steam 凭据、重新认证、请求商店或写入 Steam 收藏。

## 当前候选的验证

- 本地完整 Python：**129 项通过，35.797 秒**；Node：**24 项通过**。包括真实 worker 的 503→200、429→200、重试耗尽、慢速响应总截止、取消及进程退出、旧指针保护；未以 Mock 状态重试代替真实传输回归。
- 本机 Python **3.14.2**、Node **22.19.0**；`pip check` 通过。
- 源码凭据模式扫描通过；它不扫描 Git 历史及忽略的本地产物，不等同于完整安全审计。`git diff --check main..HEAD` 通过。
- 精确候选 SHA 的 [CI 36509475419](https://github.com/lovewtong/steam-library-toolkit/actions/runs/36509475419) 已重新核验，Windows/Linux/macOS 全部 SUCCESS；CI 使用 Python 3.12、Node 22，执行完整 Python/Node 和源码凭据扫描。三平台离线测试不代表三平台真人认证已通过。
- 固定 R1 样本重放 **31/31** 符合预期，内置规则 **28** 条；沿用 R1 的证据分级，没有将离线重放当作重新查询商店或全库准确率测量。
- 重新校验 R3 的 collected/enriched/refreshed/view 四个 current 指针及其全部 manifest 文件哈希；再用干净候选离线重建独立运行：**388 条记录、377 个 game、27 条未知总时长**。原始记录及两套分类除 run_id 外均不变，picker 与收藏计划内容一致，源指针不变。账号、成员清单、运行编号及完整核验结果仅保存在本机 R4 产物目录。

本次本地回归命令：

```powershell
.\.venv\Scripts\python.exe -B -X utf8 -m unittest discover -s tests -p "test_*.py"
npm test
.\.venv\Scripts\python.exe -B -X utf8 -m pip check
.\.venv\Scripts\python.exe -B -X utf8 tools/check_secrets.py
git diff --check main..HEAD
```

## R1–R3 证据适用性

R1 的生产修改止于 `1662c7a`。从该提交到候选只增加文档、公开聚合基准结果和独立基准工具，没有修改生产模块、分类规则、依赖声明或 CI。R2 在 `1662c7a` 测量的传输实现、R3 在 `a4095be` 验证的生产流程与当前候选相同；本次复核确认这些证据仍适用，不将它们改写为在新 SHA 上重新进行的在线实测。

R2 冷缓存 582.236 秒与暖缓存中位 0.843 秒是指定环境的一组基线，不承诺其他网络、机器、规模或账号性能。R3 是 Windows 单账号独立安装链路，未证明任意账号的全集完整性。R4 文档交付提交仍须核验其自己的三平台 CI；R5 合并前应按最终 SHA 再次确认检查结果，不能只引用本报告的旧运行编号。

## 远端关系与 R5 交接

本次实时核验 [PR #5](https://github.com/lovewtong/steam-library-toolkit/pull/5) 仍 OPEN，head 为 `a923f5035f98d7e2592841868f9dbdb29407cc1f`，base 为 main，mergeStateStatus=CLEAN，六项既有检查 SUCCESS。当前候选包含 PR #5 的全部提交，并在其后追加 F06–F10 及 R1–R3；候选分支当前没有自己的 PR。**仅合并 PR #5 不会交付后续分类、时间字段、收藏计划和验收改动。**本次未创建或合并 PR、创建标签或 Release。

R5 应先刷新主线、两条分支及 PR 状态，明确完整候选的整合方式，避免遗漏或重复整合；按授权合并后，对最终 main 核验差异、精确提交 CI 及 R1–R4 证据适用性。然后完成发布说明、已测版本、迁移步骤、旧写回停用说明及版本/标签准备。若整合产生生产变化，补做受影响的回归或真人验收。

仍保留的限制：未迁移的名称启发式及细分类可能误判；全库人工准确率未知；多账号/多设备、Families、自然权益变化、macOS/Linux 真人认证和自动收藏写回均未完成验收。README 的 Python 3.10+/Node 18+ 最低版本声明尚无对应版本矩阵证据，R5 必须明确区分最低声明与实际验证版本。这些边界不得被“R4 通过”抹去。
