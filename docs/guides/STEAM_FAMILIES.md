# Steam Families：采集范围与来源

`main` 的客户端采集默认加入家庭来源。此功能尚未包含在已发布的 v1.1.0 中，该版本标签保持 `88ce73b`。首次观察与家庭两个 PR 的复审记录见 [整合复审](../validation/PR12_PR13_REVIEW.md)。

## 使用

登录并保持 Steam 在线，使用已有的客户端采集命令：

```powershell
.\.venv\Scripts\python.exe steam_collect.py --local-session --no-store --strict-membership -o outputs/family-library.json
.\.venv\Scripts\python.exe steam_enrich.py --input outputs/family-library.json -o outputs/family-enriched.json
.\.venv\Scripts\python.exe steam_picker.py --serve --input outputs/family-enriched.json
```

客户端模式默认读取家庭来源。首次请求前后确认账号仍属于同一个家庭，核对每个应用的所有者都在家庭内，读取两次清单并比较 AppID、类型、排除原因和所有者。只有 `app_type=1` 且 `exclude_reason=0` 的游戏能通过家庭来源加入成员；原客户端返回的 application/demo/beta 等记录仍保留。许可候选不能单独决定当前成员。

需要原来的客户端限定范围时，使用 `--no-family -o outputs/client-only.json`。家庭库输出不能被这个较窄范围覆盖，必须使用独立路径。`--owned-only` 仍是 API 过滤选项，不能代表客户端的“只包含自己购买”。API-only 和离线导入不调用家庭接口。

## 审计与未知值

- 默认可信运行使用 `membership=accessible_snapshot`、`membership_semantics=client_and_family_games`；显式 `--no-family` 沿用 `client_snapshot`。
- 每条记录的成员来源为 `client_library` 或 `family_library`；自有与共享重叠时优先保留客户端成员来源，并附家庭证据。
- `family_evidence` 只保存是否本账号所有、是否有其他家庭所有者、所有者数量和共享资格，不保存家庭 ID、名称或其他成员账号。家庭与 CM 的所有权证据冲突时显示 `ownership=unknown`，保留双方证据。
- `family_library` 的“确认未加入家庭”是成功的空来源；缺少列表、账号不符、家庭/权益变化、响应达到请求上限或网络失败均不能作为空库。家庭核验失败时不发布客户端子集，旧指针不变。
- 家庭新成员的首次观察来自本次来源时间；已有同账号历史继续保留。家庭接口的 `rt_time_acquired`、`rt_playtime` 和 `rt_last_played` 不直接填入个人购买日期、分钟数或最近游玩字段。个人来源没有时长时保留 `null`。
- 表格、复核清单、本地页面、离线重分类、元数据补全和收藏计划接受相同的成员规则。计划记录两个来源的观察时间以及共享 AppID，仍只导出，不写回 Steam。

请求使用 `max_apps=100000`；达到上限或出现后续分页/截断标记会拒绝本轮结果。接口没有协议完成标记，两次一致仅证明本轮观察稳定，不能证明全家庭、所有应用或当前可启动状态完整。每个 HTTP 调用最多 35 秒，家庭四次调用共享 90 秒预算，沿用有限重试与冷却。采集父进程的总预算与取消机制仍有效。

## 兼容性

旧的带校验运行仍可读取和重分类。新家庭运行在 schema v2 中增加成员枚举和证据字段，旧软件可能明确拒绝它；回退使用旧软件配旧运行，或用 `--no-family` 生成独立客户端库。完整备份保留 `.current.json` 与对应隐藏运行目录。独立家庭快照重建仍是历史候选，不能升级为实时成员证明。

## 验证

2026-10-06 在干净采集提交 `8c5350f7ff1761c375f8b26500b9c15853b0d363` 上完成真实本地登录采集，没有使用临时探测适配器。得到 829 条（818 game），保留原 388 条，新增 441 条家庭游戏。两款参照均为 `family_library` / `shared`，本账号个人时长分别为 111、163 分钟，来源为 `client_last_played_times`，没有采用家庭接口时长；460 条缺少个人总时长的记录保持未知。

公开商店补全仅请求两个参照 AppID，两项成功。`b2aeacc74580a52e68764cef4909fb14cbe0ceb8` 干净提交上离线重分类、表格、picker、复核清单和收藏计划一致；页面两款均显示家庭共享、实际家庭来源和 UTC 首次观察日期。参考游戏的主类与子类按第一方依据校正，其他字段仍保持未知或生成状态，不作全库人工准确率声明。

完整记录及局限见[账号场景](../validation/REAL_SCENARIO_VALIDATION.md)。离线回归覆盖未知时长、错误账号、家庭/所有者变化、排除、截断、长冷却、截止、失败保留指针、范围缩窄保护、历史继承和各输出一致性；这些模拟故障不能代替真人权益变更验收。

协议依据是[公开 FamilyGroups 定义](https://github.com/SteamDatabase/Protobufs/blob/master/steam/steammessages_familygroups.steamclient.proto)，不属于 Steam 对第三方工具的稳定接口承诺。[Steam Families FAQ](https://help.steampowered.com/en/faqs/view/054C-3167-DD7F-49D4)说明可共享范围以及使用限制。
