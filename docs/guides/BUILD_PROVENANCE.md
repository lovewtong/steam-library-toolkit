# 包版本与构建标识 / Package build identity

运行审计、current 指针、摘要、快照和失败诊断中的 `producer` 增加三个可选字段。既有 `git_commit`、`dirty` 含义保持不变，旧运行不需要重写。

| 字段 | 含义 |
|---|---|
| `package_version` | 源码运行读取当前项目版本；安装版读取已安装 distribution 版本。无法确认时为 null |
| `build_id` | 安装包版本及代码、资源内容的 `sha256:<64 hex>` 标识。只有当前安装内容匹配构建记录时提供 |
| `build_status` | `source`：源码运行；`verified`：安装内容匹配；`unavailable`：旧 wheel 无记录；`invalid`：记录无效或不可读取；`modified`：安装内容变化 |

源码运行继续记录其 checkout 的 Git 提交和 dirty 状态，`build_id=null`。安装版的 Git 字段继续为 null，不读取数据目录或当前工作目录的 Git。构建标识本身不推定源码提交；发布或验收记录需要保存完整提交、wheel SHA-256、包版本和 build_id 的对应关系。

构建时生成 `resources/build-info.json`。算法将版本、按区分大小写的 POSIX 相对路径顺序排列的文件名和各文件的原始字节哈希纳入标识，排除该记录自身以及 Python 字节码缓存。运行时重新核对当前安装内容。改变代码、资源、文件名或版本会改变标识；移动安装位置、创建字节码缓存不改变标识。换行等原始字节变化也会影响结果，因此不同平台构建不保证 ID 相同。

wheel SHA-256 标识归档文件字节；build_id 标识安装后的版本与包内容。压缩时间等归档差异可能改变 wheel SHA-256，保持相同的包内容标识。两者用于追溯和完整性检查，均不是数字签名。

旧 wheel 没有构建记录时，版本仍可查，标识保持 null，不阻断原有工作流。无效记录或修改过的安装内容不冒充原构建；审计会保存相应状态。历史 parent_run、旧指针和旧产物保持其原 producer，新操作记录当前 producer。

## English

The optional `package_version`, `build_id` and `build_status` fields are added to `producer` in audits, current pointers, summaries, snapshots and failure diagnostics. Existing Git fields and old runs remain compatible.

Source execution reads the version from its project and retains checkout Git information, with no installed build ID. Wheel execution reads the installed distribution version, verifies `resources/build-info.json` against the actual package payload, and leaves Git fields unknown. It does not infer a source commit from the working directory. Acceptance and release records associate the full source commit, wheel SHA-256, package version and build ID explicitly.

The deterministic identity covers the version, file names sorted by case-sensitive POSIX relative paths and raw code/resource bytes, excluding the identity record itself and bytecode caches. Relocation and bytecode generation do not change it; payload, file-name or version changes do. Raw line-ending differences can produce different IDs across platforms. Wheel SHA-256 identifies archive bytes; build_id identifies installed package contents. Neither is a digital signature.

Statuses are `source`, `verified`, `unavailable`, `invalid` and `modified`. Older wheels without a record remain usable with an unknown build ID. Invalid records and modified payloads do not claim the original build ID. New operations record their own producer while preserving historical parent-run evidence.
