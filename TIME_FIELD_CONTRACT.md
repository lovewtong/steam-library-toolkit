# 最近游玩证据与 API 未知时间契约

## 表格中的最近游玩（F08）

最近游玩以 playtime_evidence.rtime_last_played 为准，独立于总时长的证据。分类表格 JSON 保留 last_played_at、last_played_iso，并添加 last_played_status、last_played_source、last_played_observed_at。CSV 在既有列后追加原始时间戳和三个证据列；Markdown 添加状态、来源和观察时间列。

| 状态 | 显示 | 含义 |
|---|---|---|
| known_nonzero | 日期 | 本轮来源提供正时间戳 |
| known_zero | 无时间记录 | 来源明确给出零；不能进一步推断从未玩过 |
| historical | 历史 日期（零时为历史 无时间记录） | 从快照取得，不是本轮重新核验 |
| unknown | 未知 | 缺少该时间字段；不借用总时长的 known 状态 |
| unverified | 未核验 日期 | 旧平面输入有日期但没有字段证据，不补造来源或观察时间 |

时间戳为零不会格式化为 1970 年日期。存在字段证据时，用证据值生成 UTC 日期，不使用可能冲突的旧 last_played_iso。观察时间指来源当时的 fetched_at，而非本次分类或读取时间。

示例：API 本轮提供总时长 5 分钟、最近游玩 null，快照提供 1700000000。CSV 中 playtime_status=known，而 last_played_status=historical，显示“历史 2023-11-14”，保留来源 license_file 和快照观察时间。classified.json 和表格均在同一运行中保存并受 manifest 哈希校验保护。原始库、成员和采集证据不修改；旧产物需离线重新分类才会获得新列。

## 三个 API 时间字段（F09）

Node 与 Python 对 playtime_forever、playtime_2weeks、rtime_last_played 使用同一契约：

- 字段缺失保持缺失；显式 null 保持 null，表示未知，不变为零。
- 0 与正整数保留原值；上限 4294967295。
- 布尔值、负数、小数、数字字符串、数组、对象及越界值继续拒绝，不静默转成未知。
- 单条合法 null 不使整个来源失效，也不丢弃同来源其他游戏的有效时长。来源合并仍可选择其他来源的有效字段，保留历史标记。

共用测试数据为 tests/fixtures/api-time-values.json，Python 与 Node 分别通过实际适配入口消费它。此契约仅针对三个时间字段，不宣称所有 API 响应形状已完全统一，也未声称 Valve 当前线上一定会发送 null。

本次不进行真实 Steam 认证、权益变化或收藏写回。历史最近游玩问题通过合成来源合并、不可变发布及 CSV/Markdown 检查验证。

本轮本地完整回归：109 项 Python、24 项 Node 通过。修复前新增用例已复现历史状态缺失与 Node null 导致 RESPONSE_INVALID；修复后通过。远端验证必须按本轮提交独立查询，不能复用分类提交的 CI 结果。
