# v1.3.0：范围冻结 / Frozen scope

范围冻结日期：2026-10-07。**候选提交待定，尚未创建标签或 Release。** 当前构建版本仍为 `1.3.0.dev0`；正式版本和完整候选 SHA 在代码复审、主线 CI 与版本准备完成后另行冻结。v1.2.0 继续固定在 `044a435a27023034071ac460965b5013fe37df3d`。

## 纳入范围

- PR #15／#16 已合并的 `src/steam_library_toolkit` 源码包、资源归位、wheel/sdist 构建和安装后命令。
- 八个常用根目录 Python 命令的兼容入口；支持 `steam-library`、直接 executable 和 `python -m steam_library_toolkit`。
- 源码与安装版的数据目录约定、`STEAM_LIBRARY_HOME`、独立 Node 运行目录和显式依赖准备。
- 运行审计中的包版本、构建身份和校验状态；旧运行兼容，安装版不冒认当前工作目录的 Git。
- 延续 v1.2.0 的采集、审计、补全、分类校正、浏览、收藏计划导出，以及厂商、首次观察和家庭成员规则。

本版不加入新的采集来源或分类规则，不增加购买日期推定、自动 Steam 写回、安装器、自动更新或 PyPI 发布。多账号、离线恢复、自然权益变化、Linux/macOS 真人认证、全家庭覆盖、逐游戏启动和全库分类准确率仍保留原有证据边界，不因源码包化而升级承诺。

## 已有证据

`9b332573fc2767b692373eba40631eaf603a5665` 干净主线的 `1.3.0.dev0` wheel 在全新 Windows Python 3.14.2 虚拟环境中安装，独立准备 Node 22.19.0 依赖。真实本机授权采集及复测得到 829 条、818 game、441 共享、460 条个人时长未知；两轮成员与观察历史一致。DOOM: The Dark Ages（3017860）和 Space Marine 2（2183900）均为 family_library/shared。两款实际商店请求、重分类、页面 HTTP/API、计划 dry-run／导出与复核清单通过，旧运行与配置未变。

这份真人证据属于引入构建标识前的上述提交。新的构建标识需要在包含该功能的干净提交和 wheel 上独立验收；不能把旧结果直接归给新候选。个人库和原始日志保留本机，公开文档只记录结果与适用范围。

## 发布门槛

| 任务 | 目标与状态 |
|---|---|
| 构建标识代码与文档复审 | 完成字段兼容、变更检测、sdist/直接 wheel 一致及三平台 CI；本变更待复审 |
| 新构建安装验收 | 在干净提交上构建并安装，核对版本、wheel 哈希、build_id 和旧数据；保留独立真实家庭采集记录 |
| 主线整合 | 受影响 PR 按依赖复审后合并，核验精确主线提交的三平台 CI |
| 正式版本与候选冻结 | 将开发版本更新为 1.3.0，明确完整候选 SHA、tree 和构建记录；不可自动采用分支 HEAD |
| 最终候选验收 | 重跑候选相关构建、安装、旧数据升级及旧软件＋旧运行回退；真实验收证据绑定该候选 |
| 发布 | 完成双语说明、公开源码／wheel 归档核验、标签 CI 和匿名下载检查后另行发布 |

若发现范围内阻塞问题，修复、复审并更新候选及对应证据；范围外功能留待后续版本。源码与 wheel 是本版交付形态，不承诺自动安装或更新。源码内的私人账号配置、缓存、运行和 node_modules 不进入归档。

## English

Scope frozen on 2026-10-07; the candidate commit is pending and no v1.3.0 tag or Release has been created. The current package version remains `1.3.0.dev0`. The full candidate SHA and final version will be chosen explicitly after review and main CI. v1.2.0 remains unchanged.

Scope includes the merged source/resource layout, wheel/sdist installation, installed commands and eight compatible source entries, data-directory and Node-runtime setup, package build provenance, and the existing v1.2 workflows. New acquisition sources, classification batches, purchase dates, Steam writes, installers, auto-updates and PyPI publication are excluded. Existing live-validation limits remain.

The clean `9b33257` wheel already passed Windows one-account local-session family collection and repeat/history checks: 829 records, 818 games, 441 shared and 460 unknown playtimes. The two reference games, real two-app enrichment, reclassification, HTTP page/API, review and plan exports passed. This evidence predates build provenance and is not automatically evidence for a later candidate.

Release gates are code review and multiplatform CI, independent clean-build installation acceptance, main integration, explicit final-version/full-SHA freeze, candidate upgrade/rollback validation, and bilingual notes plus public archive/tag/download checks. New features require a separate scope decision; private data and installed dependencies are excluded from distributed archives.
