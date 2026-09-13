# 分类人工核对记录（2026-09-13）

本轮针对商店补全后表格仍为“其他”的 14 个项目。7 个获得带官方来源的 AppID 校正，7 个保留待核对。加上先前 500、550、730，内置规则共 10 条。以下分类是本项目的编辑判断，并非 Steam 官方分类名称。

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

| AppID | 名称 | 当前缺口与后续动作 |
|---|---|---|
| 15150 | Petz Catz 2 | 支持页可确认名称，但本轮未取得 PC 版玩法的一手依据；需核对 PC 版官方手册，避免套用其他平台版本。 |
| 205930 | Hitman: Sniper Challenge | 旧 picker 名称规则为狙击；尚未补齐对应 AppID 的官方玩法证据，表格保持其他。 |
| 622590 | PUBG: Test Server | 需核对测试应用与正式游戏的官方关系，再决定分类继承规则。 |
| 654310 | For Honor - Public Test | 同上；不能只凭名称覆盖应用类型或当前成员资格。 |
| 770720 | Hunt: Showdown 1896 (Test Server) | 商店补全返回成功但 genres 为空；需核对测试应用关系及分类继承。 |
| 813000 | PUBG: Experimental Server | 需单独核对实验分支关系，不能把另一个测试 AppID 的结论直接套用。 |
| 2871050 | Endless halo | 本轮搜索主要找到第三方聚合信息，未取得可核对的官方玩法介绍；不按名称推断为 Halo 系列。 |

“待核对”表示本轮证据未闭合，不表示无法修复，也不表示这些项目不存在自动分类。旧 picker 名称启发式仍可能提供分类；表格与 picker 的所有非校正项尚未统一。

## 名称规则与回归

原来直接使用子串匹配，`Konami` 会命中 `kona`，`Shanked` 会命中 `shank`。现在匹配前移除商标符号、统一大小写和空白，并要求匹配词两侧不是词字符。保留最长规则优先与系列后缀匹配；相同完整词语仍不能保证 AppID 身份，人工规则始终以 AppID 为准。

本机已有库离线重建验证：388 条记录、377 个 game；表格“其他”从 14 降至 7，27 条未知时长保持未知。除新 run_id 外原始记录字段完全一致。现有库名称规则命中仍为 265，所有名称规则结果与修改前相同。新增回归覆盖无名称/无 genres 的人工样本、词内误匹配、商标、空白、系列及具体作品优先。

这不是全库准确率评测。仍需扩大独立人工样本、迁移名称规则到 AppID，并完成字段覆盖、补全性能与真实多环境认证验证；第三阶段整体尚未完成。
