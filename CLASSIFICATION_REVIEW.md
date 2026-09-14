# 分类人工核对记录（2026-09-13）

针对商店补全后表格仍为“其他”的 14 个项目，第一轮校正 7 个，第二轮再校正 4 个测试分支，目前 3 个保留待核对。加上先前 500、550、730，内置规则共 14 条。以下分类是本项目的编辑判断，并非 Steam 官方分类名称。

## 已加入规则

| AppID | 名称 | 表格主分类 / picker 子类 | 核对依据 |
|---|---|---|---|
| 241930 | Middle-earth: Shadow of Mordor | 动作/冒险 / 开放世界动作 | [商店](https://store.steampowered.com/app/241930/Middleearth_Shadow_of_Mordor/)动作、冒险和开放世界标签 |
| 326480 | If My Heart Had Wings | 独立/其他 / 视觉小说 | [商店](https://store.steampowered.com/app/326480/If_My_Heart_Had_Wings/)视觉小说介绍 |
| 627270 | Injustice 2 | 动作/冒险 / 格斗 | [商店](https://store.steampowered.com/app/627270/Injustice_2/)格斗与动作标签 |
| 745960 | A Sky Full of Stars | 独立/其他 / 视觉小说 | [商店](https://store.steampowered.com/app/745960/A_Sky_Full_of_Stars/?l=brazilian)视觉小说标签 |
| 923810 | If My Heart Had Wings -Flight Diary- | 独立/其他 / 视觉小说 | [MoeNovel 公告](https://store.steampowered.com/news/posts/?appids=923810&enddate=1550567325)六篇可选故事 |
| 976310 | Mortal Kombat 11 | 动作/冒险 / 格斗 | [商店](https://store.steampowered.com/app/976310/Mortal_Kombat_11?l=english)格斗与动作标签 |
| 1971870 | Mortal Kombat 1 | 动作/冒险 / 格斗 | [Steam 身份](https://store.steampowered.com/app/1971870/Mortal_Kombat_1/)及[官网玩法](https://www.mortalkombat.com/en-id/game) |

视觉小说暂映射到现有“独立/其他 → 独立/叙事”展示组，不断言开发商或发行商的独立性。此命名存在歧义，后续分类体系统一时应改善。这里只确认主分类和子类，未核对所有氛围、强度、推荐语或多人等标签。

## 保留待核对

第二轮重新请求这 7 个项目的公开 appdetails：6 个 success=false，Hunt 测试服 success=true 但缺少 genres。随后核对官方公告，解决以下 4 项：

| AppID | 分类 | 依据 |
|---|---|---|
| 622590 | 射击 / 战术竞技射击（测试分支） | [PUBG 开发团队 PC 1.0 Update #3](https://steamstore-a.akamaihd.net/news/externalpost/steam_community_announcements/2356940714976801833)说明测试服、正式服更新关系与地图/武器变更 |
| 813000 | 射击 / 战术竞技射击（实验分支） | [PUBG Corp. Sanhok Testing Patch Notes #4](https://steamstore-a.akamaihd.net/news/externalpost/steam_community_announcements/2396358621996509996)明确实验服及 FPP/TPP、投掷武器玩法 |
| 654310 | 动作/冒险 / 冷兵器动作（测试分支） | [Ubisoft Public Test Meta Changes](https://www.ubisoft.com/en-us/game/for-honor/news-updates/1IZoiczWorTTTsrEYprgzR/public-test-meta-changes)解释测试环境和攻防战斗系统 |
| 770720 | 射击 / 战术射击（测试分支） | [该 AppID 下 Crytek 的 Update 1.13 公告](https://steamstore-a.akamaihd.net/news/externalpost/steam_community_announcements/5151601211226205949)说明测试服枪械及射击场 |

AppID 与名称取自已经核验的客户端库；玩法和分支关系依据官方公告进行人工判断。只为这些确切 AppID 添加规则，不按名称自动继承所有测试应用，不修改 app_type、成员或权益。历史测试公告不证明测试服今天仍能连接。

剩余 3 项：

| AppID | 名称 | 当前缺口与后续动作 |
|---|---|---|
| 15150 | Petz Catz 2 | Steam 商店及 manual/15150 入口当前重定向首页，未取得 PC 版官方玩法依据；仍需旧版手册。 |
| 205930 | Hitman: Sniper Challenge | 官方新闻接口找到 IO Interactive/Nixxes 补丁公告，可确认产品但未完整说明玩法；旧 picker 狙击规则保留，尚未迁移 AppID。 |
| 2871050 | Endless halo | 本轮搜索主要找到第三方聚合信息，未取得可核对的官方玩法介绍；不按名称推断为 Halo 系列。 |

“待核对”表示本轮证据未闭合，不表示无法修复，也不表示这些项目不存在自动分类。旧 picker 名称启发式仍可能提供分类；表格与 picker 的所有非校正项尚未统一。

## 名称规则与回归

原来直接使用子串匹配，`Konami` 会命中 `kona`，`Shanked` 会命中 `shank`。现在匹配前移除商标符号、统一大小写和空白，并要求匹配词两侧不是词字符。保留最长规则优先与系列后缀匹配；相同完整词语仍不能保证 AppID 身份，人工规则始终以 AppID 为准。

第一轮本机已有库离线重建验证：388 条记录、377 个 game；表格“其他”从 14 降至 7，27 条未知时长保持未知。除新 run_id 外原始记录字段完全一致。现有库名称规则命中仍为 265，所有名称规则结果与修改前相同。第二轮加入四个测试分支后，“其他”降至 3。新增回归覆盖无名称/无 genres 的人工样本、词内误匹配、商标、空白、系列及具体作品优先。

这不是全库准确率评测。仍需扩大独立人工样本、迁移名称规则到 AppID，并完成字段覆盖、补全性能与真实多环境认证验证；第三阶段整体尚未完成。
