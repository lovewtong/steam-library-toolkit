# 按 AppID 校正分类

人工校正只修改分类展示，不改变库成员、应用类型、时长或采集时间。修改名称或使用本地化名称不会影响 AppID 匹配。

仓库内 `classification_overrides.json` 保存有来源的内置规则；`classification_overrides.local.json` 保存个人偏好，已被 Git 忽略。可复制 `classification_overrides.example.json` 后编辑。文件必须为 schema_version=1，apps 的键是规范十进制 AppID。

每条规则必须提供 `main_category`、`reason`，可选 `reference`、`sub`、`vibe`、`intensity`、`slogan`。字符串会去掉首尾空白；不接受重复键、未知字段、空理由、无效 AppID 或时长/成员字段。`intensity` 只能是低、中、高。本地条目整体替换同 AppID 的内置条目，未填写的字段不会暗中继承内置校正。

| main_category（表格） | primary（picker） |
|---|---|
| 射击 | 射击 (FPS/TPS) |
| 动作/冒险 | 动作/冒险 |
| RPG | 角色扮演 (RPG) |
| 策略、模拟经营 | 策略/模拟 |
| 休闲/益智 | 解谜/休闲 |
| 体育/竞速 | 体育/竞速 |
| 独立/其他 | 独立/叙事 |
| 其他 | 其他 |

表格主分类决定 picker 主分类的映射，所以一条校正不会在两个入口分别定义互相矛盾的主分类。基础 genres 映射已共用 classification_rules.py；五维的 KNOWN 名称启发式仍可优先于 genres，不等于两套输出已完全统一。

主类改变时，未指定的 sub/vibe 重置为“待核对”、intensity 为“未知”，推荐语重新生成。只修改 sub 时，未指定推荐语也重新生成。主类不变时可以保留旧细项，但证据继续标为规则推断，不能当成人工确认。显式提供的字段优先。

classification_evidence.fields 为每个五维字段（表格为 main_category/tags）分别记录 source/state/reason/reference；state 为 reviewed、inferred、unknown 或 generated。只有规则明确提供的字段标 reviewed，reference 只属于这些字段；它表示规则声明的审核范围，不证明引用自身已被程序验证。表格 tags 继续来自规则，主类校正不会把 tags 也标为人工确认。

## 应用到现有库

可先用 [主类待复核清单](CLASSIFICATION_REVIEW_QUEUE.md) 查看保存分类的差异、未知项及名称规则依据，再决定需要校正哪些 AppID。该清单不会自动接受或写入规则。

```powershell
.\.venv\Scripts\python.exe steam_reclassify.py --input steam_enriched.json -o steam_reclassified.json
.\.venv\Scripts\python.exe steam_picker.py --serve --input steam_reclassified.json
```

重建完全离线，需要已有可信客户端成员运行及其 current.json 指针，输出必须独立。每个新运行保存实际命中的 `classification_overrides.json`，纳入产物哈希校验；审计记录 override_count、父运行和 classification_rebuild 操作。五维 JSON 保留 classification_evidence；新增 classified.json 保存完整表格结果与逐字段依据，纳入 manifest 哈希。picker API 及页面的“分类依据”展示各字段状态；旧产物缺少字段证据时不补造人工审核记录。CSV 的既有列保持兼容，理由可在运行规则文件中按 AppID 查询。

修改本地规则不会重写旧运行；必须重新分类或重新采集/补全，再让 picker 使用新目标。独立的两个分类脚本也使用同一规则，但其平面输出不会自动替换 picker 已核验的运行。

## 当前覆盖与限制

内置规则现有 34 条：原 16 条、R1 新增 12 条、[批次 01](CLASSIFICATION_BATCH_01.md) 新增 6 条。R1 固定 31 项样本保持不变，新批次独立保存；所有注册样本共同覆盖全部内置规则的改名和字段证据检查。R1 记录见 [R1_CLASSIFICATION_REVIEW.md](R1_CLASSIFICATION_REVIEW.md)，早期逐项来源与分类取舍见 [CLASSIFICATION_REVIEW.md](CLASSIFICATION_REVIEW.md)。这些是明确的校正样本，不代表全库准确率。

原有 KNOWN 名称规则尚未全部迁移到 AppID；早期记录的“其他 14→3”属于历史产物。R1 固定样本中 2 项仍为未知，4 项仅沿用历史证据，不能将不同样本计数混用。名称匹配已增加词边界及商标/空白规范化，但仍是启发式。元数据字段状态、类别 ID 与有限并发见 [补全说明](METADATA_ENRICHMENT.md)；未知时长研究和自动收藏写回仍为后续工作。
