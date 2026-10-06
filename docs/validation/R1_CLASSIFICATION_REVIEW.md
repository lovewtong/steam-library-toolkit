# R1 分类质量复核（2026-09-28）

## 结论与范围

固定 31 个 AppID 样本已完成本轮复核及针对性整改；修复前 13 项与编辑预期不符，修复后 31 项输出符合预期。新增 12 条 AppID 校正，内置规则由 16 增至 28，全部纳入改名及字段依据一致性检查。

**这不是 100% 分类准确率。** 样本为风险导向选择：原 16 条人工规则、3 个待核对项目、7 个名称规则样本和 5 个 genres 推断样本。样本在第一方资料复查及代码修改前冻结，没有删除失败项目或增加容易通过的替代项。审阅以表格主类、picker 主类与子类为界；氛围、强度、推荐语和多人/手柄标签没有全部人工核对。

证据分开计数：25 项本次取得可读第一方页面或其检索内容；4 项仅沿用历史已记录证据，本次受入口不可获取/年龄页影响未能重取正文；2 项仍无充分玩法证据，保持未知。样本自动回归检查预定的输出和证据契约，不自动验证网页真实性或新鲜度。

## 发现与处理

- Caveman World 的“文明建设”、One Gun Guy 的“roguelike 射击”、Lair Land Story 的“地牢经营”、Destroyer 的“潜艇模拟”没有得到对应官方玩法描述支持，已改为精确 AppID 规则。
- BROK 保留点击冒险与清版动作的混合玩法；Wrestledunk 改为体育合集；Broken Age、Deponia 的表格与 picker 使用同一解谜展示组。Planet Coaster 按主要经营玩法选类。这些是项目编辑判断，不是 Steam 官方分类的逐字翻译。
- Date Everything 的恋爱模拟、Squirrel with a Gun 的沙盒射击/解谜平台，不再使用“经营模拟”细分。
- Hitman: Sniper Challenge 取得 Square Enix Windows 版狙击说明，并以 Steam 的 [205930 EULA](https://store.steampowered.com/eula/205930_eula) 核对标题，新增 AppID 规则。没有认证、兑换或启动游戏。
- Petz Catz 2 仍缺 PC 版第一方玩法依据，移除宽泛名称规则；Endless halo 继续保持未知，不按名称与 Halo 系列关联。两个项目都留在样本和库中。
- 移除 7 个已迁移作品的名称规则，以及未经确认的 Petz Catz 规则，避免对其他 AppID 或续作继承这些结论。Hitman 原本正确的狙击名称规则保留为 inferred，精确 AppID 校正优先。
- 通用子类推断不再把“模拟”标签或名称中的 sim 子串等同于经营；没有更具体依据时回到未知细分，防止 Simple 等词误命中。其余名称启发式并未全部消除。

“模拟经营”仍是项目既有 Simulation 粗类，包含舰船/恋爱/角色养成等模拟；“独立/其他 → 独立/叙事”仍是旧展示映射，不能据此判断发行商独立性。以上命名歧义保留为后续分类体系改进，不将其冒充已解决。

## 固定清单：预期与修复后的实际一致

每行三个值依次为表格主类 / picker 主类 / picker 子类。修复后的实际值由离线工具逐项比较，下表记录预期。refreshed=本次可读来源；historical_not_refreshed=历史证据保留；unavailable=当前证据不足。正式分类字段的 reviewed 表示曾有编辑核对，不代表当前重新读取了网页。

| AppID | 名称 | 入选来源 | 58b4428 输出 | 编辑预期与修复后输出 | 本次来源状态 | 依据与处理 |
|---|---|---|---|---|---|---|
| 500 | Left 4 Dead | existing_override | 射击 / 射击 (FPS/TPS) / 合作生存射击 | 射击 / 射击 (FPS/TPS) / 合作生存射击 | refreshed | [来源](https://store.steampowered.com/app/500/Left_4_Dead/)；开发商介绍四人合作对抗感染者，商店 FPS 标签支持射击。 |
| 550 | Left 4 Dead 2 | existing_override | 射击 / 射击 (FPS/TPS) / 合作生存射击 | 射击 / 射击 (FPS/TPS) / 合作生存射击 | refreshed | [来源](https://store.steampowered.com/app/550/Left_4_Dead_2/)；开发商简介明确为合作动作恐怖 FPS。 |
| 730 | Counter-Strike 2 | existing_override | 射击 / 射击 (FPS/TPS) / 竞技战术射击 | 射击 / 射击 (FPS/TPS) / 竞技战术射击 | refreshed | [来源](https://store.steampowered.com/app/730/CounterStrike_2/)；商店竞技目标玩法、烟雾和 FPS 标签支持该项目分类。 |
| 15150 | Petz Catz 2 | unresolved | 其他 / 策略/模拟 / 宠物模拟 | 其他 / 其他 / 待核对 | unavailable | [来源](https://store.steampowered.com/app/15150/)；未取得 PC 版第一方玩法说明；移除未经身份核对的 Petz Catz 名称规则，不跨平台推断。 |
| 205930 | Hitman: Sniper Challenge | unresolved | 其他 / 射击 (FPS/TPS) / 狙击 | 射击 / 射击 (FPS/TPS) / 狙击 | refreshed | [来源](https://www.jp.square-enix.com/company/ja/news/2012/html/3049753882ca456c6f7a6dc6157286b4.html)；Square Enix 2012-10-05 公告包含 Windows，说明玩家使用狙击步枪暗杀目标；Steam EULA 205930 确认标题身份。 |
| 214340 | Deponia | genre_rules | 动作/冒险 / 动作/冒险 / 多种元素 | 休闲/益智 / 解谜/休闲 / 点击冒险 | refreshed | [来源](https://store.steampowered.com/app/214340/Deponia/?l=english&u=)；开发商喜剧冒险介绍与商店 Point & Click/Puzzle 标签；采用项目解谜展示组，与 Broken Age 统一。 |
| 230410 | Warframe 星际战甲 | genre_rules | RPG / 角色扮演 (RPG) / 多种元素 | RPG / 角色扮演 (RPG) / 多种元素 | refreshed | [来源](https://store.steampowered.com/app/230410/Warframe/)；官方 Genre 包含 Action/RPG，现有 RPG 粗类可接受；未将泛化子类当作已完成细分，也未排除射击成分。 |
| 232790 | Broken Age | known_name | 动作/冒险 / 解谜/休闲 / 点击冒险 | 休闲/益智 / 解谜/休闲 / 点击冒险 | refreshed | [来源](https://www.doublefine.com/games/broken-age)；Double Fine 官网将本作定义为 Point & Click Adventure，统一表格与 picker 主类。 |
| 241930 | Middle-earth™: Shadow of Mordor™ | existing_override | 动作/冒险 / 动作/冒险 / 开放世界动作 | 动作/冒险 / 动作/冒险 / 开放世界动作 | refreshed | [来源](https://store.steampowered.com/app/241930/Middleearth_Shadow_of_Mordor/)；开发商战斗冒险介绍与商店 Open World/Action 标签支持现有编辑分类。 |
| 326480 | If My Heart Had Wings | existing_override | 独立/其他 / 独立/叙事 / 视觉小说 | 独立/其他 / 独立/叙事 / 视觉小说 | refreshed | [来源](https://store.steampowered.com/app/326480/If_My_Heart_Had_Wings/)；MoeNovel 简介明确为 animated visual novel；独立/叙事是现有展示组，不判断发行商性质。 |
| 462960 | Caveman World: Mountains of Unga Boonga | known_name | 动作/冒险 / 策略/模拟 / 文明建设 | 动作/冒险 / 动作/冒险 / 2.5D平台跳跃 | refreshed | [来源](https://store.steampowered.com/app/462960/Caveman_World_Mountains_of_Unga_Boonga?l=french)；开发商介绍复古 2.5D 平台冒险、越障和关卡；文明建设规则错误。 |
| 493340 | Planet Coaster | genre_rules | 策略 / 策略/模拟 / 经营模拟 | 模拟经营 / 策略/模拟 / 主题公园经营 | refreshed | [来源](https://store.steampowered.com/app/493340/Planet_Coaster/?l=english)；开发商说明主题公园建造、过山车设计和游客管理，按主要玩法选择模拟经营而非泛策略。 |
| 622590 | PUBG: Test Server | existing_override | 射击 / 射击 (FPS/TPS) / 战术竞技射击（测试分支） | 射击 / 射击 (FPS/TPS) / 战术竞技射击（测试分支） | historical_not_refreshed | [来源](https://steamstore-a.akamaihd.net/news/externalpost/steam_community_announcements/2356940714976801833)；沿用 2026-09-13 核对的 PUBG PC 1.0 Update #3 与 AppID 身份记录；本次原公告及社区入口无法获取，不记为重新验证。 |
| 627270 | Injustice™ 2 | existing_override | 动作/冒险 / 动作/冒险 / 格斗 | 动作/冒险 / 动作/冒险 / 格斗 | refreshed | [来源](https://store.steampowered.com/app/627270/Injustice_2/)；官方 Legendary Edition 介绍格斗、角色阵容与对局，支持格斗细分。 |
| 654310 | For Honor - Public Test | existing_override | 动作/冒险 / 动作/冒险 / 冷兵器动作（测试分支） | 动作/冒险 / 动作/冒险 / 冷兵器动作（测试分支） | refreshed | [来源](https://www.ubisoft.com/en-us/game/for-honor/news-updates/1IZoiczWorTTTsrEYprgzR/public-test-meta-changes)；Ubisoft Public Test Meta Changes 解释测试环境与攻防系统；AppID 身份沿用已核验旧记录，不证明服务器仍可用。 |
| 745960 | A Sky Full of Stars | existing_override | 独立/其他 / 独立/叙事 / 视觉小说 | 独立/其他 / 独立/叙事 / 视觉小说 | refreshed | [来源](https://store.steampowered.com/app/745960/A_Sky_Full_of_Stars/)；官方商店叙事介绍和 Visual Novel 标签支持现有展示组，不把氛围及强度当作已复核。 |
| 770720 | Hunt: Showdown 1896 (Test Server) | existing_override | 射击 / 射击 (FPS/TPS) / 战术射击（测试分支） | 射击 / 射击 (FPS/TPS) / 战术射击（测试分支） | historical_not_refreshed | [来源](https://steamstore-a.akamaihd.net/news/externalpost/steam_community_announcements/5151601211226205949)；沿用 2026-09-13 核对的 Crytek Update 1.13 测试服枪械与射击场证据；本次公告入口无法获取。 |
| 813000 | PUBG: Experimental Server | existing_override | 射击 / 射击 (FPS/TPS) / 战术竞技射击（实验分支） | 射击 / 射击 (FPS/TPS) / 战术竞技射击（实验分支） | historical_not_refreshed | [来源](https://steamstore-a.akamaihd.net/news/externalpost/steam_community_announcements/2396358621996509996)；沿用 2026-09-13 核对的 PUBG Sanhok Testing Patch Notes #4；本次公告入口无法获取，不代表分支仍在线。 |
| 923810 | If My Heart Had Wings -Flight Diary- | existing_override | 独立/其他 / 独立/叙事 / 视觉小说 | 独立/其他 / 独立/叙事 / 视觉小说 | refreshed | [来源](https://store.steampowered.com/app/923810/If_My_Heart_Had_Wings_Flight_Diary/?l=german)；直接入口受区域限制；本次可检索官方商店发行方介绍：六篇独立可选故事，无故事内分支。 |
| 949480 | BROK the InvestiGator | known_name | RPG / 解谜/休闲 / 点击冒险 | 动作/冒险 / 动作/冒险 / 点击冒险/清版动作 | refreshed | [来源](https://store.steampowered.com/app/949480/BROK_the_InvestiGator/)；COWCAT 介绍明确融合调查解谜、清版动作及 RPG 元素；项目按混合冒险归类，避免只有点击冒险或单列 RPG。 |
| 976310 | Mortal Kombat 11 | existing_override | 动作/冒险 / 动作/冒险 / 格斗 | 动作/冒险 / 动作/冒险 / 格斗 | historical_not_refreshed | [来源](https://store.steampowered.com/app/976310/Mortal_Kombat_11?l=english)；沿用 2026-09-13 已核对的商店格斗规则；本次商店入口仅返回年龄页，未重复确认正文。 |
| 1200580 | One Gun Guy | known_name | 动作/冒险 / 射击 (FPS/TPS) / roguelike 射击 | 动作/冒险 / 动作/冒险 / 动作平台跳跃 | refreshed | [来源](https://store.steampowered.com/app/1200580?l=english)；开发商描述一个大型关卡、升级、障碍、Boss 和多难度的动作平台游戏；未找到 roguelike 依据。 |
| 1268140 | Lair Land Story | known_name | 策略 / 策略/模拟 / 地牢经营 | 模拟经营 / 策略/模拟 / 角色养成/视觉小说 | refreshed | [来源](https://store.steampowered.com/app/1268140/Lair_Land_Story/?curator_clanid=32977561)；发行商描述安排 Chilia 四年的日程、成长和选择；地牢经营及龙与地下城措辞错误。 |
| 1272010 | Destroyer: The U-Boat Hunter | known_name | 模拟经营 / 策略/模拟 / 潜艇模拟 | 模拟经营 / 策略/模拟 / 驱逐舰反潜模拟 | refreshed | [来源](https://store.steampowered.com/app/1272010/Destroyer_The_UBoat_Hunter/?curator_clanid=39457373)；开发商描述指挥 Fletcher 级驱逐舰、护航及反潜；玩家操作的不是潜艇。模拟经营是项目现有 Simulation 粗类，不断言有经营系统。 |
| 1301520 | Wrestledunk Sports | known_name | 体育/竞速 / 动作/冒险 / 体育搞怪 | 体育/竞速 / 体育/竞速 / 多人体育合集 | refreshed | [来源](https://store.steampowered.com/app/1301520/Wrestledunk_Sports/)；开发商介绍击剑、摔跤、Smashball 等多人体育项目；统一体育主类，移除篮球推荐语。 |
| 1966970 | Ingression | existing_override | 动作/冒险 / 动作/冒险 / 精确平台跳跃 | 动作/冒险 / 动作/冒险 / 精确平台跳跃 | refreshed | [来源](https://store.steampowered.com/app/1966970/Ingression/)；开发商明确传送门与精确平台跳跃；复查历史误分类修复。 |
| 1971870 | Mortal Kombat 1 | existing_override | 动作/冒险 / 动作/冒险 / 格斗 | 动作/冒险 / 动作/冒险 / 格斗 | refreshed | [来源](https://www.mortalkombat.com/en-id/game)；官方玩法页介绍主战角色、Kameo 辅助、招式及格斗行动；Steam 身份沿用已核验记录。 |
| 2067050 | Squirrel with a Gun | genre_rules | 模拟经营 / 策略/模拟 / 经营模拟 | 射击 / 射击 (FPS/TPS) / 沙盒射击/解谜平台 | refreshed | [来源](https://store.steampowered.com/app/2067050/Squirrel_with_a_Gun/)；开发商简介明确 sandbox shooter 和 puzzle platformer；经营模拟细分不符。 |
| 2201320 | Date Everything! | genre_rules | 模拟经营 / 策略/模拟 / 经营模拟 | 模拟经营 / 策略/模拟 / 恋爱模拟 | refreshed | [来源](https://store.steampowered.com/app/2201320/Date_Everything/?curator_clanid=3182421)；发行商明确 sandbox dating simulator；保留项目 Simulation 粗类，纠正无依据的经营细分。 |
| 2202120 | 63 Days | existing_override | 策略 / 策略/模拟 / 即时战术/潜行 | 策略 / 策略/模拟 / 即时战术/潜行 | refreshed | [来源](https://store.steampowered.com/app/2202120/63_Days/)；发行方介绍战术、潜行、团队操作及 Real Time Tactics 标签；复查历史错误名称规则。 |
| 2871050 | Endless halo | unresolved | 其他 / 其他 / 待核对 | 其他 / 其他 / 待核对 | unavailable | [来源](https://store.steampowered.com/app/2871050/)；商店入口不可获取，受限第一方检索没有结果；不凭 Halo 名称猜测，不以未知证明下架或不存在。 |

原 16 条规则除上述来源可访问性差异外，主类和子类均保持；本轮没有悄悄修改其历史核对日期或宣称重新验收服务器可用性。4 项历史记录见 [前次核对](CLASSIFICATION_REVIEW.md)。

## 可重复检查

公共 fixture 只包含公开游戏身份、分类输入、冻结的旧输出、编辑预期、来源和处理说明，不包含账号、拥有关系、时长、令牌或个人规则。全部校正规则检查显式读取内置 JSON，避免个人配置改变回归期望。

```powershell
python -B tools/review_classification_sample.py -o outputs/r1-classification/report.json
python -B -m unittest discover -s tests -p "test_classification*.py"
```

[固定样本](../../tests/fixtures/classification-r1.json) 与 [检查工具](../../tools/review_classification_sample.py) 可离线运行，不联网、不认证。报告保存 actual/expected/baseline、逐字段依据和来源状态；比较失败返回非零退出码。新增 6 项测试覆盖固定分层、独立编辑预期、全部规则改名、无关同名 AppID、Simulation 反例，以及不可变发布→表格→picker→收藏计划链路。

## 全库影响与验收边界

对已保存的 388 条历史记录做离线分类对比，仍只选择 377 个 game：五维内容变化 25 项，其中主类 7、子类 24、氛围 10、强度 8、推荐语 10；表格主类变化 7 项。这些字段变化可能来自清除错误名称规则后的推断/未知回退，不能全部称为新人工判断。

其中 13 项在固定样本之外：SKYHILL、Just Deserts、World of Warships、House Flipper、Bus Simulator 21 Next Stop、Pharaoh: A New Era、Zero Hour、ACROBATIC CAR、Core Keeper、SteamWorld Build、Deckline、Cube Foundry、Alterchase。12 项撤回“经营模拟”到未知细分；ACROBATIC CAR 去掉较早的模拟匹配后落到原有竞速推断，仍是 inferred。这些项目需要今后单独核对，没有计入本次 25 项新来源复查。

本轮完整 129 项 Python、24 项 Node 通过，其中分类专项为 22 项；源码凭据模式及 diff 检查通过。新增测试在修改前复现固定样本不符和模拟误判，修改后通过。干净提交的个人库离线重建另在本机保存 comparison.json，不能用上述分类预演冒充真实账号重新采集。个人运行及完整比较报告仅保留本机 outputs/r1-classification；公开固定样本不是个人拥有清单。R2 性能、R3 Windows 真实端到端及 R4/R5 最终发布仍待执行。
