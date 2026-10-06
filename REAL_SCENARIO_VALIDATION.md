# 真实账号场景：2026-10-05

最新状态：2026-10-06 已完成生产家庭来源修复、两款参照真实复测及[整合复审](PR12_PR13_REVIEW.md)。当前 `main` 包含修复，已发布的 v1.1.0 不包含；下述 2026-10-05 失败记录保留为修复前证据。

本次使用 Windows 上已登录的账号，只读采集和查询。功能基线为干净提交 `83e6183536e9e230659520df506662091f57cf83`。未切换账号、退出家庭、制造退款、启动游戏或写入 Steam 收藏。

## 已验证的部分

严格客户端采集得到 388 条记录：377 game、5 application、2 demo、4 beta。Web API 有 358 条，许可来源有 2435 条；这些是不同来源的数量，不能相互代替。27 条总时长仍为未知。

从同账号的旧完整运行继承首次观察历史，388 条均有历史日期；表格、页面、CLI 筛选和收藏计划一致。保存运行可以在阻断网络连接的验证中离线读取和重新分类，原始字段除新运行 ID 外保持，源指针和 manifest 哈希未变。独立快照仍生成候选库，不升级成当前成员证明。

干净文档提交 `582b5d2` 另验证厂商与时间组合。独立缓存副本补全后，页面 `2K + 2026-09` 为 13 款，再选择 `2K Australia` 为 4，改为 10 月为 0，恢复为 4；表格、picker 和计划一致，成员、类型、时长、日期及历史账本不变，旧缓存和源指针受保护。这不重新认证或刷新所有权。

## 已复现：Steam Families 游戏遗漏

用户确认已加入 Steam 家庭，并提供两款本人未购买、当前家庭库可玩的参照游戏：

| 游戏 | AppID | 正式采集结果 | 家庭库接口探测 |
| --- | --- | --- | --- |
| [DOOM: The Dark Ages](https://store.steampowered.com/app/3017860/) | 3017860 | 缺失 | 存在，`exclude_reason=0`，所有者不包含当前账号 |
| [Warhammer 40,000: Space Marine 2](https://store.steampowered.com/app/2183900/) | 2183900 | 缺失 | 存在，`exclude_reason=0`，所有者不包含当前账号 |

只读探测使用现有认证进程取得的短期访问凭据，调用 `IFamilyGroupsService/GetFamilyGroupForUser` 和 `GetSharedLibraryApps`。核对当前账号在家庭中、清单返回的 `owner_steamid` 为当前账号、前后家庭 ID 未变化；两次 AppID、所有者与排除状态一致。凭据、家庭 ID 和其他成员账号没有写入公开记录。

这是临时测试适配器取得的结果，**生产采集尚未接入该来源**。当前 `GetClientAppList(fields=games)` 返回集和 `GetOwnedGames` 均未提供这两个条目；CM 许可候选已包含它们，审计的 `license_not_client` 中也都有记录。当前成员选择只以经过核验的客户端 RPC 集合为准，因此许可候选被排除，最终输出缺失。单纯启用 `excludeShared:false` 无法改变这个成员选择规则。

`status=ok` 和 `--strict-membership` 表示现有来源通过其接口核验，不表示与 Steam 界面家庭库全集相等。这次 V04 判定为失败；39 条有共享许可证据的自有记录也不能替代仅共享游戏验证。两款参照证实了遗漏和可行的数据来源，不能证明全部家庭游戏已核对，更没有进行实际启动测试。

协议字段与排除原因可在[公开协议定义](https://github.com/SteamDatabase/Protobufs/blob/master/steam/steammessages_familygroups.steamclient.proto)中核对；这不是 Steam 对第三方工具的稳定接口承诺。Steam 官方说明家庭游戏会出现在客户端游戏库中，见 [Steam Families FAQ](https://help.steampowered.com/en/faqs/view/054C-3167-DD7F-49D4)。

## 下一项修复及验收

| 任务 | 目标与完成条件 |
| --- | --- |
| FAM-01 家庭来源适配 | 只读接入家庭身份与清单；核对账号、家庭前后状态、重复读取和截断风险；无家庭、接口不可用、确认空列表分别表达 |
| FAM-02 成员与所有权契约 | 单独定义可访问家庭库与自有库；允许有依据的共享成员进入所选范围，保留 source/ownership；排除条目和其他所有者不得冒充当前账号购买 |
| FAM-03 日期与时长证据 | 新共享记录首次观察只取本次可信观察；`rt_time_acquired` 不直接当购买日期，`rt_playtime` 在单位及账号语义确认前不转换成现有分钟字段 |
| FAM-04 安全与故障回归 | 错误账号、家庭变化、所有者变化、429/超时、截断、排除项与输出中断测试；失败不静默回退成“完整家庭库”，保留旧运行 |
| FAM-05 真实验收 | 在干净修复提交重新采集，核对两款参照均出现且为共享；确认自有成员保留、分类/页面/计划一致、运行哈希和原指针受保护；仍注明未逐游戏启动验证 |

收藏计划是否支持包含家庭来源的运行，要随 FAM-02 明确验证，不能直接绕过现有客户端成员检查。家庭 API 的 `max_apps`、省略列表和响应结束条件也必须研究，不能仅凭两次一致就宣布完整。

## 仍未完成的真人场景

| 场景 | 当前状态 | 下一次验证条件 |
| --- | --- | --- |
| 多账号 A→B→A | 暂无第二账号，未验证 | 用户有第二账号时，在独立输出中手动切换；当前模拟隔离测试不代替真人验收 |
| Steam 自身离线→在线 | 未切换客户端离线状态 | 在用户方便时手动切换；已完成的是保存数据离线恢复 |
| 自然权益变化 | 没有本次可用的前后事件 | 遇到新增/撤销/共享变化时保存前后运行，不人为退款或退出家庭 |
| 家庭库完整性 | 两款遗漏已复现，尚未修复 | 完成 FAM-01–05 后重测 |

完整个人产物和临时探测脚本保留在本机 `outputs/observations`，不提交到仓库。当前测试不代替其他系统真人认证或加入新来源后的性能验收。


## 家庭修复真实复测：2026-10-06

采集基线 `8c5350f7ff1761c375f8b26500b9c15853b0d363`，`producer.dirty=false`。使用生产 helper、Windows `--local-session --no-store --strict --strict-membership --require-source family_library`，继承同账号历史，输出独立库与快照；没有临时适配器或 `NODE_OPTIONS` 注入。未切换账号、退出家庭、启动游戏或写入 Steam 收藏。

| 数量口径 | 结果 |
| --- | --- |
| 原客户端成员 | 388，全部保留 |
| 家庭原始响应 | 1073，包含排除项和非游戏，不直接作为库数量 |
| 共享资格和 game 类型通过核验 | 779，其中 338 与客户端重叠 |
| 新增家庭来源游戏 | 441 |
| 合并输出 | 829：818 game、5 application、2 demo、4 beta |
| 所有权观察 | 388 本账号许可、441 共享，本次无证据冲突 |
| 本账号总时长 | 369 已知、460 未知，0 历史 |
| Web API / CM 许可候选 | 358 / 2435，未作为成员全集 |

两次家庭清单及前后家庭成员/角色核验通过；原始 AppID、类型、所有者和排除资格稳定。请求上限 100000，本次未达到，仍记录 `semantic_completeness_proven=false`。829 条不是完整 Steam 界面库的逐项人工核对结果。

| 参照 | 修复后成员与所有权 | 本账号时长 | 首次观察与校正 |
| --- | --- | --- | --- |
| DOOM: The Dark Ages，3017860 | present / family_library / shared，own=false，排除原因 0 | 111 分钟，client_last_played_times | 2026-10-06 UTC；射击 / 动作FPS |
| 星际战士2，2183900 | present / family_library / shared，own=false，排除原因 0 | 163 分钟，client_last_played_times | 2026-10-06 UTC；射击 / 第三人称射击 |

个人时长已有独立客户端依据；共享资格不代表时长必须未知。没有个人依据时仍为 null，没有从家庭所有者的 `rt_playtime` 或 `rt_time_acquired` 推断购买时间或分钟数。

仅对两款参照调用公开商店补全，两项成功，没有执行新增全库冷缓存性能基准。随后在干净 `b2aeacc74580a52e68764cef4909fb14cbe0ceb8` 上离线重分类。复测发现《星际战士2》被泛 RPG 标签错误归类；根据 [Focus 发售公告](https://www.focus-entmt.com/en/news/warhammer-40000-space-marine-2-launches-today-prepare-for-war-with-the-launch-trailer)及 [Bethesda 揭晓文章](https://slayersclub.bethesda.net/en-EU/news/doom-the-dark-ages-revealed)，仅为这两个 AppID 校正主类与子类，并新增独立编辑 fixture。氛围、强度和推荐语不冒充人工确认。

818 条分类成员在表格、picker、复核清单与计划一致。10 月计划包含 441 个新观察游戏，两款参照均在其中；页面名称与 2026 年/10 月组合各返回一款，展示共享及家庭来源。元数据补全与离线重分类保留成员、所有权、个人时长和首次观察历史。旧 live/combined/offline 指针及全部 manifest 文件、采集源指针均未变，所有新 manifest 哈希通过。旧 388 条的名称、类型、三个时间值与首次观察证据保持。新产物不含 token、家庭 ID 或其他成员账号字段。

FAM-01–05 实现与两款参照验收通过，修复已进入 `main`，尚未发布。家庭核验失败拒绝发布较小客户端子集；`--no-family` 必须使用独立范围，不能覆盖家庭库。故障和家庭变化保护来自离线回归，未制造自然权益变化。多账号、Steam 自身离线恢复、实际启动与全家庭逐项核对仍未验收。

个人结果、哈希记录、验证脚本和两张页面截图在本机 `outputs/observations/family-*`；不提交完整个人库。采集及发布共 32.075 秒，只是本次观测，不能当作网络性能承诺。详见 [Steam Families 契约](STEAM_FAMILIES.md)。
