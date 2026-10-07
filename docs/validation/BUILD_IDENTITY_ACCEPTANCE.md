# 安装包构建身份验收 / Installed build identity acceptance

2026-10-07，在干净提交 `d639954e9050d059c33e4b2b7ab7bb66cca233de` 上构建开发版 wheel，安装至新的 Windows 虚拟环境，并使用独立数据目录完成验收。这是开发提交的验收记录；v1.3.0 正式版本与候选提交尚未冻结。

## 构建对应关系

| 项目 | 记录 |
|---|---|
| 包版本 | `1.3.0.dev0` |
| wheel | `steam_library_toolkit-1.3.0.dev0-py3-none-any.whl` |
| wheel SHA-256 | `85026967a85d6dff10d24ac5884e2757ebc1e43137bd4500484922f3f251a92b` |
| build_id | `sha256:627f91ef32837c99e20f4b2d96598b65895b6b32d9cef5f6384a03392548aeac` |
| Python / Node | Windows Python 3.14.2 / Node 22.19.0 |
| 安装内容 | 54 个包文件；非 editable 安装；隔离 Node 依赖 |

独立脚本从 wheel 文件名与原始字节重新计算内容哈希，与构建记录一致；安装后的 `build_status=verified`，Git 字段为 null。源码提交与 wheel 的对应关系来自本验收记录，包本身不推定 Git 提交。标识不包含个人数据，也不是数字签名。

## 回归与真实采集

- 180 项 Python、36 项 Node 回归通过。文档链接、源码凭据模式和 diff 检查通过。
- sdist 构建与直接 wheel 的包内容一致；安装后的 Schema、规则、HTTP 503→200 重试、HTML/API、重分类、复核、计划及八个旧命令入口通过。
- 安装资源修改后状态为 `modified`，不提供原 build_id；还原后恢复 `verified`。旧 wheel 无标识时仍可使用。
- 使用安装后的 console 命令、生产本地授权路径与原有代理，执行 `--local-session --no-store --strict --strict-membership --require-source family_library`，从旧运行继承观察历史。
- 首轮因 `PICS_UNAVAILABLE` 未通过严格模式，未发布 current 指针；实际失败诊断正确记录构建身份。相同严格参数重试成功，退出码 0，采集耗时 55.228 秒。这个时长不包含安装或商店补全，不是全库网络性能基准。
- 829 条记录，818 game、5 application、2 demo、4 beta；441 条共享记录，460 条个人总时长未知。许可、个人库、家庭库、游玩记录和 API 均 complete；全集完整性仍未证明。
- DOOM: The Dark Ages（3017860）与 Space Marine 2（2183900）均核验为 `family_library/shared`，本人持有为 false，共享可用证据已核验。
- 对照先前安装版真实运行，成员无增减，829 条首次观察时间与证据保留。旧运行、配置与个人校正文件哈希不变。
- audit、current、summary、snapshot 的 producer 一致。旧运行与新运行分别重分类后，记录除 run_id 外不变；新操作使用当前构建身份，parent_run 保留原 producer。离线失败诊断也通过身份核对。

真实日志、wheel、账号库和原始核验记录保留本机，未加入仓库。本次未执行 Steam 收藏写回。本轮真人结果只适用于上述 Windows 单账号、家庭可访问场景；没有新增多账号、离线恢复、自然权益变化或其他系统真人认证证据。

正式发布前仍需复审、精确主线 CI、最终版本与候选冻结，以及绑定该候选的安装、升级／回退与归档验收，详见 [v1.3.0 发布计划](../releases/V1_3_RELEASE_PLAN.md)。

## English

A clean `d639954e9050d059c33e4b2b7ab7bb66cca233de` development wheel was installed into a fresh Windows Python 3.14.2 environment with isolated Node 22.19.0 dependencies. The version, wheel SHA-256 and independently verified payload ID are recorded above. Installed producer fields report `verified` and leave Git information unknown. This record maps the wheel to its source commit; neither hash is a signature.

180 Python and 36 Node tests passed. Distribution checks covered sdist/direct-wheel parity, installed workflows, HTTP retry, eight compatible source entries, modified-resource detection and restoration. Older runs and wheels remain usable.

The first real local-session attempt failed strict validation with `PICS_UNAVAILABLE`, preserved existing outputs and recorded the correct build identity. Retrying the same strict parameters succeeded in 55.228 seconds: 829 records, 818 games, 441 shared and 460 unknown personal playtimes. Both reference games were verified as family-only shared entries. All enabled live sources were complete, but exhaustive library completeness remains unproven.

Membership and all 829 first-observation histories matched the earlier installed run. Audit, pointer, summary, snapshot and failure diagnostics carried consistent producer evidence. Reclassification preserved rows and historical parent producers. Old outputs and personal configuration remained unchanged. Private account data and logs were not committed; no Steam writes occurred.

This acceptance covers the named development commit and one Windows family account. It is not acceptance of a final v1.3.0 candidate, multiple accounts, offline recovery, natural entitlement changes or live authentication on other platforms.
