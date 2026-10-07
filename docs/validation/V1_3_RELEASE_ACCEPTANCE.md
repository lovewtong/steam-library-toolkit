# v1.3.0 发布前验收 / Prepublication acceptance

验收完成日期：2026-10-08。冻结候选为 `09b6d4aaf645c54a83b6c5fa132eb1378954319c`，tree 为 `9a8064783a21011c4bc846ffa906d55f7c2086c1`。正式包版本 `1.3.0`，标签 `v1.3.0` 固定到此提交。Release 为已核验草稿，尚未公开发布；此前 v1.2.0 标签与公开附件保持原样。

## 构建与 CI

- [候选主线 CI](https://github.com/lovewtong/steam-library-toolkit/actions/runs/37647055981)、[标签 CI](https://github.com/lovewtong/steam-library-toolkit/actions/runs/37648932017)：Windows、Linux、macOS 各 180 Python／36 Node，通过文档、凭据模式扫描和分发检查。
- 从干净 Git 归档构建，162 个源码文件的路径与 Git blob 逐一匹配。54 个安装文件的 sdist／直接 wheel 内容一致；八个旧源码入口通过。
- wheel SHA-256：`475e71b2b7009b9d09be294312fc5408bd2fdac0b58bc98516b42b73ac9fcf29`。
- build_id：`sha256:c2c0c21db5e4e1d3bf99c7d160ca5fd0b72b652715c7a7e2bcc088a3343de8c8`。安装 producer 的 package_version=1.3.0、build_status=verified；git_commit／dirty 为未知，未借用工作目录的 Git 信息。
- Windows Python 3.14.2 全新虚拟环境安装正式 wheel，独立准备 Node 22.19.0；安装命令、资源、依赖和诊断通过。

构建哈希校验内容，不构成签名。源码 ZIP 绑定冻结 Git tree，wheel 哈希绑定本次实际交付包；之后提交的冻结文档不属于这 162 个文件，也不会移动候选或重建附件。

## 升级与回退

实际旧版本为 v1.2.0（`044a435a27023034071ac460965b5013fe37df3d`），旧运行与其 producer 一致。先备份旧软件、完整隐藏运行目录、current 指针、配置和个人规则，再用新软件读取备份、写到独立输出。

829 条记录的值、类型、权益、来源、未知时长与观察日期保留；表格、页面和计划按 AppID 比较一致，parent_run 保留旧 producer。个人分类 fixture 应用后生效，撤销后恢复原结果。最后使用实际旧软件重新读取旧备份，与升级前结果一致。旧输出、指针和配置按哈希核对未变，数据验收阶段无网络或 Steam 写回。

回退合同是「旧软件＋旧数据备份」，没有承诺旧软件读取任意新格式。Python 包更新不会迁移数据或替换独立 Node 目录；升级时使用新的环境及数据／Node 目录，再切换。

## 候选真实场景

全新安装版调用生产 `collect --local-session --no-store --strict --strict-membership --require-source family_library`，显式选择已有授权账号并继承旧观察历史，首轮成功，耗时 25.842 秒。

| 项目 | 本次结果 |
|---|---|
| 记录／类型 | 829：818 game、5 application、2 demo、4 beta |
| 共享记录／未知个人时长 | 441／460 |
| 客户端清单／家庭清单／API | 388／779／358，各来源返回状态 complete |
| 与基线成员／日期 | 增删均为 0；829 条首次观察时间及证据保留 |
| 两款商店补全 | 2 成功、0 缓存命中；5.211 秒，仅两款直取 |
| 审计与输出 | manifest 哈希核验通过，installed producer 一致 |

DOOM: The Dark Ages（3017860）与 Space Marine 2（2183900）均为 family_library/shared，非本人拥有，成员状态已核验；个人时长分别为 111／163 分钟，来源 client_last_played_times。两款厂商信息通过真实商店请求取得，主分类及子类由已复核 AppID 规则给出；氛围／强度保持未知，生成建议不冒充人工证据。

家庭核验使用两次一致响应及账号／所有者／家庭关系检查。协议未提供完成标记，`semantic_completeness_proven=false`；来源 complete 不能被解释为已经与全家庭 UI 穷举对齐。

表格、页面/API、收藏计划与复核清单均为 818 game。重分类没有改变成员、权益、个人时长或历史日期。实际 console dry-run 前后文件集合与哈希不变，计划及复核清单导出通过；没有 Steam 收藏写回或启动游戏。

## 实际页面与剩余未知

浏览器操作安装版页面，按名称＋发行商＋2026 年 10 月分别筛到两款参照，各一条；切到 11 月得到零条。未知发行商为 816 条，明确空发行商为零条，分类证据展开与安装／源码启动说明通过。页面/API 的结果与导出按 AppID 核对一致。截图与私人账号输出只保留本机。

本次只为两款游戏请求商店信息，不是全库元数据覆盖率或冷缓存性能验收。复核清单有 782 条待检查、36 条未入队；未入队不等于所有字段经过人工验证。分类质量、未知字段和来源继续可查，不宣称全库分类准确率。首次观察仍是工具观察时间，不是购买或家庭入库时间。

## 附件与发布状态

草稿六个附件：源码 ZIP、sdist、wheel、双语说明、脱敏验收 JSON、SHA256SUMS。附件全部回下载与原文件逐字节及 SHA-256 核对一致，草稿正文、目标提交和标签对应正确。匿名下载 GitHub 标签归档并核验全部 162 个 Git blob；个人库、原始日志、配置、凭据和 node_modules 未上传。

**公开发布后仍需检查 Release 页面、六个附件的匿名下载和 SHA256SUMS。** 草稿附件回下载使用维护者授权，不算公开访问验收。发布前状态保存在[候选记录](../../releases/v1.3.0-candidate.json)，不能将此记录当作已经发布的通知。

未真人验证：多账号切换、离线恢复、自然权益变化、Linux/macOS 认证、全家庭 UI 穷举、实际游戏启动和全库冷缓存性能。本版不包含 Steam 自动写回、购买日期推定、安装器、自动更新或 PyPI 发布。

## English

Prepublication acceptance completed on 2026-10-08 for the full commit and tree above. Both exact-main and tag CI passed on three platforms (180 Python and 36 Node tests each). A canonical 162-file Git archive produced a 54-file payload; sdist/direct-wheel parity, eight compatibility entries and fresh Windows installation passed. The recorded wheel digest and verified build identity bind evidence to this candidate; subsequent documentation does not move the tag or rebuild assets.

Upgrade testing preserved an entire real v1.2.0 generation and compared records, dates, evidence, table/picker/plan, parent producers and personal correction/revocation. Actual v1.2 software read the preserved old data before and after. Old pointers, artifacts and configuration remained unchanged. Rollback means old software plus its old backup, not arbitrary forward compatibility.

Candidate-bound live Windows collection passed on the first attempt: 829 records, 818 games, 441 shared and 460 unknown personal playtimes. All 829 observed dates were preserved. Both reference AppIDs were verified shared members; personal time came from the client's personal last-played source. Two real store requests succeeded without cache hits. Table/API/export membership, dry-run and browser name/publisher/year/month filters and unknown/empty states passed without Steam writes or launches.

This is one account and two store requests, not exhaustive family membership, full metadata coverage or a cold-library performance benchmark. Family responses have no protocol completion marker; semantic completeness is not proven. The review queue contains 782 pending items and 36 not queued; not queued is not all-field human validation. Other account/platform/recovery/entitlement scenarios remain unverified.

Six draft assets were downloaded back and matched byte-for-byte and by SHA-256. Anonymous GitHub tag-source download matched all Git blobs. The Release remains unpublished: anonymous public Release-page/asset checks must follow publication. Private account exports, raw logs and credentials remain local.
