# 分类复核批次 02

2026-10-11，在 main `162c7c1ecfd55166638362c5cffbce8d2c009a83` 上建立本地分支 `fix/classification-p1-batch-02`。对全库元数据补全后的 155 项 P1 清单进行证据核对：129 项新增 AppID 主类校正，26 项证据不足，继续保留原结果。内置规则从 36 条增至 165 条。本批是未发布的源码候选，已发布的 v1.3.0 和旧运行不变。

## 为什么表格与页面会不同

原来的 127 项差异来自五维分类的名称规则与表格的 genres 规则取舍不同，不能据此判断哪一方一定错误。有的名称规则比粗 genres 更贴近玩法，有的明显不合适，还有少数输出了分类体系之外的“冒险”主类。本批逐 AppID 决定结果，共用一条校正规则；没有整体翻转两个来源的优先级，也没有批量接受名称规则。

从 Steam 公开 appdetails 为全部 155 个 AppID 读取资料，128 个响应标为 success。这个状态只表示接口返回了数据，不表示作品身份或玩法已经确认。普通规则要求返回的 `steam_appid` 与请求一致、类型为 game，并有可读玩法介绍；少数不可用作品使用对应商店页面或官方手册。完整响应、哈希及个人复核清单只留本机。

| 例子 | 本次判断 | 依据与取舍 |
|---|---|---|
| TopSpin 2K25（1785650）、GRIP（396900） | 体育/竞速 | [TopSpin 商店资料](https://store.steampowered.com/api/appdetails?appids=1785650&l=english)、[GRIP 商店资料](https://store.steampowered.com/api/appdetails?appids=396900&l=english) 分别说明网球与赛车，覆盖原策略/模拟名称规则。 |
| 100% Orange Juice（282800） | 策略；骰子卡牌桌游 | [对应商店资料](https://store.steampowered.com/api/appdetails?appids=282800&l=english) 明确桌游、骰子和卡牌，按主要玩法归组。 |
| Rollerdrome（1294420） | 射击；轮滑第三人称射击 | [对应商店资料](https://store.steampowered.com/api/appdetails?appids=1294420&l=english) 明确第三人称射击与轮滑动作结合，采用射击粗类。 |
| Chernobylite（1016800）、Wolfstride（1331210） | RPG | [Chernobylite](https://store.steampowered.com/api/appdetails?appids=1016800&l=english)、[Wolfstride](https://store.steampowered.com/api/appdetails?appids=1331210&l=english) 的正文直接定义 RPG；没有照抄旧名称分类。 |
| F.E.A.R. 与两个扩展（21090、21110、21120） | 射击；恐怖 FPS | [官方合集手册](https://store.steampowered.com/manual/21090) 有本体及 Extraction Point、Perseus Mandate 的独立章节；扩展 API 返回本体 AppID，不能作为扩展身份的独立证明。 |
| 全面战争：幕府将军 2（34330） | 仅确认策略主类 | [对应 API](https://store.steampowered.com/api/appdetails?appids=34330&l=english) 确认身份及 Strategy；正文为空，子类仍为待核对。 |
| Portal 2 - The Final Hours（104600） | 其他；开发纪实数字书 | [对应商店页面](https://store.steampowered.com/app/104600/Portal_2__The_Final_Hours/?l=english) 的 About the Digital Book 描述数字书。没有把页面附带的 Portal 2 游戏介绍当作本 AppID 的玩法，也没有改动客户端采集的 game 类型。 |

全部 155 项的冻结预期、基线、参考链接和取舍见 `tests/fixtures/classification-batch-02.json`。主类是项目的编辑选择，混合玩法在子类中保留，不声称唯一正确的官方分类。129 条都明确确认主类，128 条同时确认子类；氛围、强度、推荐语与表格 tags 没有因此获得人工确认状态。

队列另外区分“人工确认归为其他”和“缺少依据而兜底其他”。前者不再仅因类名被算作未知；旧产物缺少逐字段证据、推断或未知状态仍会进入复核清单。

## 保存库验证

使用 2026-10-11 元数据验收的 warm3 完整运行，原 run_id 为 `2647f65a837a4ce29c13218227846222`。成员观察时间为 2026-10-07，本轮未刷新账号权益。先复制完整 generation，再用当前源码离线重建到独立目标。

| 指标 | 原运行 | 本次候选 |
|---|---:|---:|
| 库记录 / game | 829 / 818 | 829 / 818 |
| 全部主类待复核 | 782 | 653 |
| P1 项数 | 155 | 26 |
| 主类未知 | 30 | 24 |
| 表格与页面主类差异 | 127 | 3 |
| 名称启发式主类 | 244 | 120 |
| 未入主类队列 | 36 | 165 |

105 项表格主类、43 项页面主类改变。计数可能重叠；129 项退出队列不等于 129 项原分类都错误，也不等于全库准确率。

已核验原指针及所有原文件哈希不变；829 条行数据除新 run_id 外完全一致，来源审计、元数据审计和客户端快照保留原证据。689 个未选中 game 的保存分类不变。新运行的表格、picker 数据与收藏计划包含同一组 818 个 game；129 项校正后的主类映射一致，收藏主类分组逐 AppID 与页面一致。计划 dry-run 不创建文件，仍不支持写回 Steam。

候选 run_id 为 `637bde1c99164087889b6acdd555bff0`，producer 为源码 `162c7c1`、dirty=true。代码和规则实际字节摘要已冻结在本地验收记录；不能把该运行当作干净发布版本。完整个人运行、计划和报告在工作区 `outputs/classification-p1-20261011/`，不纳入 Git。

## 离线回归

```powershell
.\.venv\Scripts\python.exe tools/review_classification_sample.py --sample-set batch-02
.\.venv\Scripts\python.exe -m unittest discover -s tests -p 'test_classification*.py'
.\.venv\Scripts\python.exe -m unittest discover -s tests
npm test
```

新样本固定为 155 项：129 项有本次确认规则，26 项保留原预期及未确认状态。注册样本共同覆盖所有内置规则的改名和冲突名称输入；另一 AppID 使用相同名字不会获得人工确认。新增集成回归检查完整旧运行不变、未核对项目仍入队、字段确认范围及表格/页面/计划一致性。原 R1、批次 01 和家庭参照样本不修改。

初次候选本地 184 项 Python（46.469 秒）、36 项 Node 测试通过；其中分类专门回归为 42 项。源码凭据模式和 208 个相对文档链接检查通过。发行包检查通过：54 个包文件、sdist 对齐、安装后的分类/复核/页面数据/计划及 8 个旧入口可用。测试通过说明保存、重建和映射符合冻结预期，不能替代编辑来源复审。

## 提交前来源复审

2026-10-11，另做一次不运行规则生成脚本、不把 `expected` 当作事实来源的复核。重新核验全部 155 份原始响应摘要、121 条普通规则的精确 API 身份，以及另外 8 条手册/商店页面依据；按玩法描述检查新增 129 条规则，36 条原有规则保持不变。这是同一维护代理的独立第二遍来源检查，不是另一位审查者的第三方审核。

复核后改进了三处表达，主类决策和队列数量不变：

- Go! Go! Nippon!（251870）：所读正文定义的是 Guide Game，确认旅行导览、对话和关系发展。子类改为“旅行导览叙事”，避免把正文未明确说明的视觉小说形式标为已核对。
- Wild Terra 2（1134700）：正文明确没有预设职业。理由改为技能随使用成长和玩家控制世界，不再用容易误解为预设职业的描述；保留沙盒 MMORPG 子类。
- Gotham Knights（1496790）：正文明确 action RPG。保留动作/冒险的编辑选择，子类补为“开放世界动作/RPG混合”，避免省略所读资料中的 RPG 定义。

另外补充回归：只有表格或页面一侧的“其他”被人工确认时，另一侧仍未知的项目必须保持 P1。最终本地 185 项 Python（45.778 秒）、36 项 Node 通过，发行包、凭据模式、文档链接和 diff 检查通过。分类专项 43 项通过；远端 CI 另按精确提交记录。首次 dirty 候选及其冻结文件继续保留，不能用更新后的规则解释旧候选的具体子类结果。

## 仍需证据的 26 项

三项主类差异是 Metro 2033（43110）、Metro: Last Light Complete Edition（43160）和 Metro Exodus Enhanced Edition（1449560）。前两项本次 API 不可用；Enhanced 返回本体 412020，暂不拿本体资料确认增强版。其余未知项也没有因名称、系列关系或商店失败被强制归类。

| AppID | 项目 | 当前限制 |
|---|---|---|
| 15150 | Petz Catz 2 | 本次公开资料不足 |
| 43110 | Metro 2033 | 原版独立证据不足；主类仍有差异 |
| 43160 | Metro: Last Light Complete Edition | 完整版独立证据不足；未知与差异重叠 |
| 349040 | 火影忍者 疾风传 终极风暴4 | 本次公开资料不足 |
| 438490 | GOD EATER 2 Rage Burst | 本次公开资料不足 |
| 439700 | H1Z1: Test Server | 测试服独立玩法证据不足 |
| 460870 | GOD EATER RESURRECTION | 本次公开资料不足 |
| 524440 | The Division PTS | 测试服独立玩法证据不足 |
| 623990 | Rainbow Six Siege Test Server | 测试服独立玩法证据不足 |
| 681820 | 仙剑奇侠传四 | 本次公开资料不足 |
| 717690 | OVERKILL's The Walking Dead | 本次公开资料不足 |
| 760620 | Deiland | 本次公开资料不足 |
| 774941 | Squad 公开测试服 | 测试服独立玩法证据不足 |
| 884050 | Spring of Decadence | 本次公开资料不足 |
| 892520 | World War 3 PTE | 测试服独立玩法证据不足 |
| 998940 | 隐形守护者 | 本次公开资料不足 |
| 1007390 | 泠：落日孤行 | 本次公开资料不足 |
| 1256690 | Hot And Lovely 2 | 本次公开资料不足 |
| 1292790 | 梦中女孩 | 本次公开资料不足 |
| 1304060 | Midsummer | 本次公开资料不足 |
| 1449560 | Metro Exodus Enhanced Edition | API 返回本体，不能确认版本 |
| 1541840 | 古剑奇谭网络版 海外版 | 本次公开资料不足 |
| 1831250 | WasteLand Express 废土快递 | 本次公开资料不足 |
| 2172510 | Fairy Biography2：Confidante | 本次公开资料不足 |
| 2871050 | Endless halo | 本次公开资料不足 |
| 3417590 | Space Marine 2 Public Test Server | 测试服独立玩法证据不足 |

下一步先独立复审这批规则，再为上述 AppID 寻找可对应具体版本的开发商资料、手册或本地官方材料。测试服与本体的关系应显式留证；不能仅凭名称继承，也不能因缺少商店详情就删除库成员。P2/P3 仍在队列，未入队项目的细项也未全部人工验收。
