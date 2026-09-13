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

表格主分类决定 picker 主分类的映射，所以一条校正不会在两个入口分别定义互相矛盾的主分类。未校正项目继续使用各自原有规则，尚未统一全部分类体系。未提供的五维细项继续使用原有分类结果；这些细项不自动成为人工确认过的结论。

## 应用到现有库

```powershell
.\.venv\Scripts\python.exe steam_reclassify.py --input steam_enriched.json -o steam_reclassified.json
.\.venv\Scripts\python.exe steam_picker.py --serve --input steam_reclassified.json
```

重建完全离线，需要已有可信客户端成员运行及其 current.json 指针，输出必须独立。每个新运行保存实际命中的 `classification_overrides.json`，纳入产物哈希校验；审计记录 override_count、父运行和 classification_rebuild 操作。五维 JSON 保留 classification_evidence。CSV 的既有列保持兼容，理由可在运行规则文件中按 AppID 查询。

修改本地规则不会重写旧运行；必须重新分类或重新采集/补全，再让 picker 使用新目标。独立的两个分类脚本也使用同一规则，但其平面输出不会自动替换 picker 已核验的运行。

## 当前覆盖与限制

首批只核对了 [Left 4 Dead](https://store.steampowered.com/app/500/)、[Left 4 Dead 2](https://store.steampowered.com/app/550/) 和 [Counter-Strike 2](https://store.steampowered.com/app/730/) 的商店介绍/标签，归入射击。它们是明确的校正样本，不代表全库准确率。

原有 KNOWN 名称规则尚未全部迁移到 AppID，14 个缺少类型标签的项目也未全部人工标注。元数据字段覆盖、性能优化、认证体验、未知时长研究及收藏写回仍是第三阶段后续任务。
