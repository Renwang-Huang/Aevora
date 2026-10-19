# G20-A — 基线、来源与验证级别

本阶段任务书为 `Aevora_Gen2_G20_Final_Architecture_and_Contract_Freeze_Codex_Taskbook_2026-10-15.md`，SHA256 `001b12d27a083486553573c42850b030852d0a7bb32ed72fc23b2d316abde159`。本轮创建时间来自真实 UTC 记录，绝不回填 Git 时间。G20 只提交架构与合同；不实现 G2-1。

| 权威 | 本次现场结果 | 证据 |
|---|---|---|
| Gen1 frozen | HEAD `737f1746631774251a2c504aaf0ceafd9c3ff0c0`，Tree `7fad4fffdad4c9a85ae9e521928b6a6592a4dcb9`，clean，547 路径逐一 SHA256 匹配 | 外部 BASELINE_RECEIPT.json |
| V5C→V5C.1 | `f016a825be67c0d30c8dcdb7f6b046c26d65ca95` 是 `fc539c8524250b53af5353bfce13f1ee857b3695` 的祖先，冻结基线也是前者祖先 | merge-base 实际退出0 |
| 技术起点 | `fc539c8524250b53af5353bfce13f1ee857b3695` / `0d6bf88c0a2087b0c6ea45336c35b4d7fe67a0d2`，clean，551 个源路径匹配 | 真实 cat/show/rev-parse + 原源文件 Manifest |
| 新工作树 | `<MAINTAINER_HOME>/data_storage/aevora_validation_runs/G20-20261015T103947Z-f5d0781381/worktree`，分支 `aevora-gen2-g20-f5d0781381` | 新 bare clone --no-hardlinks；无 alternates；fsck |
| 新 Evidence | `<MAINTAINER_HOME>/data_storage/aevora_validation_runs/G20-20261015T103947Z-f5d0781381` | COMMAND_LOG.jsonl、逐命令 argv/stdout/stderr/exit |
| 1897 历史回归 | 原始 JUnit SHA `20acff431df2000ea8c6e403c6a3dfe4b140d320c5e600ded4377e7a2ff99b3f`，实际解析1897，原样历史通过 | historical_receipts；**NOT_RERUN_IN_G20** |

独立对象库属于本轮，不调用旧 registry 的 worktree add。旧 archive、原 Oracle、参考补丁和原生成绩不改。本轮 Python/SDK/SQLite/Node/Codex 仅必要 read-only probes；真实值见 source_audit/ACTUAL_READONLY_RUNTIME.json 和 commands。新 CLI feature 读取第一次因临时 CODEX_HOME 目录不存在而退出1，使用存在的临时目录后退出0，保留失败。无模型请求。

独立 V5C.1 审查文件未在限定工作目录中找到，不能声称已读。使用已封存 V5C.1 Final Report/Receipt 和当前逐文件源码复核；用户已给出的旧 V5 补充审查不能冒充新的 V5C.1 独立结论。主要风险延续：AOF139、Clock UDS EPERM、共享内核 PARTIAL、因果收益 UNKNOWN。本阶段真实 Native Multi-Agent 为 NOT_RUN。

当前维护者入口为 DEVELOPMENT.md / tools/dev.py；Product/Maintainer 工作区只改变视图，不提供安全隔离。GitHub 旧公开子集不作为源码权威；不 push、合并或改变可见性。
