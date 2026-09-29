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

自动化覆盖缓存升级、缺失/非法/空数组、失败保留、直取与缓存来源、多厂商交叉筛选、空结果、真实 CLI dry-run/导出、旧运行读取、校正冻结/撤销、CSV/picker/计划一致性与 HTML 转义。真实商店补全的本轮结果另行补记；不将旧 R2/R3 或远端 CI 的成功冒用为本次变更验收。
