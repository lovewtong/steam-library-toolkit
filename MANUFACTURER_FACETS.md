# 开发商与发行商：采集、校正、筛选和收藏计划

这是 v1.1.0 冻结目标之后的开发扩展，尚未发布。入库日期、许可日期推定和个人游玩计划不在本次实现范围。

## 字段与来源

- `developers` 与 `publishers` 是独立的名称数组，保留一款游戏的多个厂商。
- 只去掉首尾空白、去除完全相同的重复名称；不自动合并简称、大小写、子公司和母公司。
- 原始库中字段缺失或为 null 表示未知，`[]` 表示明确空数组。商店字段 missing/invalid、请求失败均不清空旧值；商店明确返回空数组可以更新旧值。
- 原始库的 `manufacturer_evidence` 保留最近一次成功应用的字段状态、来源、响应时间和读取时间。缺失/失败时保留旧证据；本轮失败仍在 audit.metadata.apps 中单独记录，不冒充再次核实。
- 分类结果保存展示值和对应证据；AppID 人工校正不会修改原始商店值。旧数据中已有名称但没有证据时标记 legacy/unverified。
- 商店响应是观察值，不保证历史开发关系或当前法律实体关系。无法取得字段时继续显示未知。

缓存升级为 v6；v5 及更早缓存按需重新请求。第一次全库补全可能较慢。旧运行仍可读取，并显示未知厂商；补全必须输出到独立目标。

## 使用

```powershell
.\.venv\Scripts\python.exe steam_enrich.py --input steam_library.json -o steam_manufacturers.json --workers 2
.\.venv\Scripts\python.exe steam_picker.py --serve --input steam_manufacturers.json
```

页面新增开发商、发行商两个筛选器，可与现有玩法、细分、氛围、强度和名称条件取交集。每款游戏显示全部厂商、来源、观察时间或校正理由；未知和明确空数组可分别筛选。一款多开发商游戏选中任一匹配开发商即可出现。

CSV 在原有列后追加 developers/publishers，值为 JSON 数组或 `null`，避免厂商名称中逗号、分号导致歧义。Markdown 与表格 JSON 同步；完整来源见 JSON 和运行审计。

## 按 AppID 人工校正

在 `classification_overrides.local.json` 中填写开发商、发行商数组与理由，可附 reference：

```json
{
  "schema_version": 1,
  "apps": {
    "7670": {
      "developers": ["2K Boston", "2K Australia"],
      "publishers": ["2K"],
      "reason": "根据该 AppID 的商店页面核对厂商名称",
      "reference": "https://store.steampowered.com/app/7670/"
    }
  }
}
```

仅提供厂商字段时不改写玩法推断。若需要保留该 AppID 的内置人工玩法校正，应同时复制需要的 main_category/sub 等字段：现有“本地条目整体替换内置条目”的规则保持不变。厂商名称也可以通过这种显式校正规则统一，不自动推断公司别名。

运行 `steam_reclassify.py --input steam_manufacturers.json -o steam_corrected.json` 后应用。每轮冻结实际校正规则；删除本地条目并再次离线重建即可撤销，原始商店观察始终保留。旧版程序不支持新增厂商校正规则；回退时使用保留的旧程序、旧配置和旧运行。

## 收藏计划

```powershell
.\.venv\Scripts\python.exe steam_sync_collections.py --input steam_manufacturers.json --account YOUR_STEAMID64 --group-by developers publishers --dry-run
.\.venv\Scripts\python.exe steam_sync_collections.py --input steam_manufacturers.json --account YOUR_STEAMID64 --publisher "2K" --group-by publishers --export-only -o manufacturers_plan.json
```

`--group-by` 可组合 intensity/primary/sub/vibe/developers/publishers，未提供时沿用原四维。`--developer`、`--publisher` 精确匹配存储的名称，两个条件取交集。不自动折叠大小写或别名。

计划保存 group_by、filters、selected_appids；eligible_appids 仍表示该可信运行中所有可分类 game。筛选为空时导出空 collections，绝不回退到全库。厂商名称使用“开发商-名称-X”等前缀，与未知/空数组分组隔离；同一游戏可属于多个厂商收藏。仍须通过账号、成员、run_id 和所有 manifest 哈希检查；dry-run 不写文件，实际 Steam 写回仍停用。

## 验证边界

自动化覆盖缓存升级、缺失/非法/空数组、失败保留、直取与缓存来源、多厂商交叉筛选、空结果、真实 CLI dry-run/导出、旧运行读取、校正冻结/撤销、CSV/picker/计划一致性与 HTML 转义。另有基准回归确保忽略读取时间差异时仍比较实际厂商值。

2026-09-29 验收：功能提交 `2f02722` 的 [三平台 CI](https://github.com/lovewtong/steam-library-toolkit/actions/runs/36587688218) 全部通过（149 Python、27 Node 和凭据模式检查）。本地前一功能提交全量 148 Python/27 Node 通过；新增的基准测试随厂商专项 5 项再次通过，并由最终 CI 执行全量。

对已保存的单账号 388 条记录进行真实公开商店请求，382 success、6 not_found；记录顺序、成员、类型、时长和旧源运行保持不变，全部 manifest 哈希通过。所有记录中开发商 377 非空/11 未知，发行商 376 非空/12 未知；其中 377 款 game 的开发商为 370 非空/7 未知，发行商为 369 非空/8 未知。成功响应也可能缺字段，因此补全状态为 partial，未猜测填充。

表格、picker 与 556 个厂商计划分组一致；逐个检查了全部 232 个发行商的精确筛选名单。实际浏览器验收：全部 377 款 → 发行商 2K 为 13 款 → 再选开发商 2K Australia 为 4 款；改选 Valve 无交集时为 0 款，再恢复为 4 款。

本次网络补全耗时 581.502 秒，但启动于未提交工作树（producer=88ce73b、dirty=true），只能作为开发验证，不能称为干净提交性能基准。随后干净 `2f02722` 缓存复核 388 次命中、0 次未命中，补全阶段 0.176 秒，厂商值与首次结果一致；该计时不包含完整发布与额外核验。私人产物保留在本机 `outputs/manufacturers`。本次没有新账号认证、所有权重新核验、真人跨系统测试或 Steam 收藏写回。
