# Full Evidence Archive 与 Audit-Lite 导出规范

## 1. 权限与保留

Full Evidence Archive 保留原始 Run、失败、完整官方事件、JUnit、真实补丁、数据库检查、指纹和命令回执。导出工具只读源归档，既不重新执行实验，也不改写过去成绩。原 M1 `TIMEOUT / PASS / TIMEOUT` 与两个独立 postmortem 是五条有不同含义的记录。

Audit-Lite 是维护者审计资产，敏感性为 `MAINTAINER_AUDIT`。包内包含测试身份、私有 Oracle 结果及调查输出，**不得发送给 Benchmark Participant**。它不包含隐藏测试源码、参考补丁源码、业务数据库、身份文件或虚拟环境。Participant 公开包和可选的维护者 Replay Pack 是不同权限级别；本轮不提供自动 Replay Pack。

归档源不迁移、不去重重写、不删除。仅在新 ZIP 中把内容相同的导出文件指向同一 `objects/<SHA256>`，再使用 Python 标准库 DEFLATE 压缩。重复 stdout 和工作区通常以 `NOT_INCLUDED` 指针保留。

## 2. 输入与输出

`benchmark.evidence_export.export_archive(full_archive, output_zip, run_ids=None, created_at=None)` 接受已封存 Full Archive。默认从 `PILOT_RESULTS.json` 与 `POSTMORTEM_RESULTS.json` 选择所有原试验和相应 postmortem，或者显式选择 Run ID。每个 Run ID 必须唯一对应其 `evaluation_report.json`。

新研究归档尚未最终封存时，可以从已停止的每 Run `run_evidence_manifest.json` 导出；其来源明确标为 `COMPLETED_RUN_SEALS`，不能宣称整个 collection 已冻结。存在 `codex-state` 的 Run 被拒绝。进行中的可信只读快照应由 Runtime status/snapshot 协议生成，不能冒充终态 Audit-Lite。

输出父目录必须已经存在，且不在 Full Archive 中。工具拒绝覆盖，先写独立临时文件，完成离线验证后以 exclusive publication 发布。源文件通过目录描述符和 `O_NOFOLLOW` 读取，拒绝软/硬链接、特殊文件、目录逃逸、单文件超过 128 MiB、选中证据超过 512 MiB，以及读取期间改变的文件。选中文件实际 SHA 必须与源 seal 一致。

### API 与独立核验

```python
from benchmark.evidence_export import export_archive, verify_bundle, inspect_bundle

receipt = export_archive(full_archive, new_zip, created_at="2026-10-10T00:00:00+00:00")
verification = verify_bundle(new_zip)
inspection = inspect_bundle(new_zip)
```

`scripts/verify_audit_bundle.py` 是仓库入口。其核心 `benchmark/evidence_verify.py` 只依赖 Python 标准库，并原字节随 ZIP 提供为 `verify_audit_bundle.py`：

```sh
python3 -I /trusted/path/evidence_verify.py verify audit.zip --json
python3 -I /trusted/path/evidence_verify.py inspect audit.zip --json
```

返回 0 表示包内一致性通过；2 表示包不安全、不完整或不一致。真正独立的审查应使用从可信维护者源码获取的 verifier，并与另一个渠道提供的 ZIP SHA 对比。**仅运行包内自带 verifier 不能认证该包来源**，因为攻击者可以同时替换内容、checksum 与 verifier。

## 3. 包结构与可证明范围

- `README_AUDIT.md`：来源、使用方法、敏感性与证明边界。
- `MANIFEST.json`：source relative path、source/export SHA 与字节数、角色、Run ID、变换策略及内容对象。
- `RUN_INDEX.json`：原 Runtime/Evaluation/Integration、版本、模型、资源策略、提交保真、协作和 postmortem 关联。
- `objects/<sha256>`：实际选中的公开输入、完整报告、JUnit、Oracle、官方 JSONL、原生 rollout、归一化时间线、实际 diff 和命令回执。
- `NOT_INCLUDED.json`：未提供原始文件的路径、SHA 与支持用途，明确 `POINTERS_ONLY_ORIGINAL_BYTES_UNVERIFIED`。
- `SHA256SUMS`：覆盖除了自身之外的全部 ZIP 成员。
- `verify_audit_bundle.py`：可移植的 stdlib verifier，来源 SHA 另行记录。

逐行 JSONL 证据完整保留，source/export line SHA 包括原换行；二次脱敏和个人路径规范化可能改变导出字节，所以 source SHA 与 exported SHA 分开。归一化事件的原始引用指向 `archive://<relative path>`，验证器核对 source line SHA 指针与导出完整行。 malformed 官方行不被补写为有效事件。

验证器检查成员与 checksum 集合、CAS 内容、Run/目录/报告引用、JUnit 真实测试 identities/counts/outcomes、pytest 退出码与 PASS、独立 Oracle 与报告、补丁 SHA/提交树保真、恢复覆盖记录和原始事件行引用。必要测试集合从与报告私有 SHA 匹配的已封存配置提取，不从实际 JUnit 反推；PASS 必须完整匹配必要集合。配置原文不装入，来源 SHA/path 单独注明；没有独立留存规格时，`suite_completeness=UNVERIFIED`。

原生子 Agent 的正面声明还要核对其第一条自身 session metadata、真实结构化 spawn/task delivery、剔除继承父历史后的完成工具活动、`task_complete`、一致的 final answer 与父 Agent typed completion receipt。Single-Agent 成功不能包含 Child；Multi-Agent PASS 至少有两个这种独立证据完整的 Child。检查用官方实际字段，不从角色名称或自然语言主述创造 Agent 身份。它不执行候选代码、不调用模型、不联网、不提取 ZIP，也不根据自然语言重新生成协作事件。

**不在包中的原始字节、脱敏前内容、模型内部权重、实际账单、历史运行来源与第三方不可变存证不能由这个包独立证明。** `NOT_INCLUDED` 是可追溯指针，不是对未提供原始文件的核验成绩；source hash 的可信起点仍为维护者 Full Archive seal 和外部来源渠道。

## 4. 可移植性、确定性与恶意包边界

统一 POSIX 相对路径，拒绝反斜杠、绝对路径、`..`、空段、控制字符、非规范 Unicode、Windows device name 和尾随空格/点。ZIP 拒绝 duplicate/case-collision、symlink、特殊成员、目录、加密、未知压缩、意外/nested 文件和不受控引用。

独立 verifier 预算为：256 MiB ZIP、10,000 成员、128 MiB 每成员、512 MiB 解压合计、2000 倍最大压缩比例。它同时检查 header 与实际读取的字节预算，不递归解包。JSON 拒绝重复 key、非有限数字和错误编码；JUnit 拒绝 DTD/entity。

ZIP timestamp 固定为 1980-01-01，成员排序固定，JSON 排序固定。显式给相同 `created_at`，同输入、verifier 与压缩库版本的输出应字节相同；未指定时刻使用实际当前 UTC，不声称跨时刻完全相同。跨不同 zlib 版本只能要求语义与内容 SHA 相同，压缩字节不保证相同。

## 5. 数据与风险

旧 M1 封存清单与实际 stat 一致：44,085 个普通文件，6,444,877,841 bytes。以既有 SHA 分组的重复估算为 18,433 条、2,582,644,201 bytes（40.07%）；它是对已封存 map 的分析，不是本次再次逐字节核验全部 6.44 GB。

JSON 4.20 GB 和日志 2.22 GB 是主要体量。轻量包选择正式三个 Pilot 及两个离线 postmortem，不把数十轮重复工作区装入；仍完整保留选中试验的评测报告及 Oracle，而非截掉失败或真实断言。实际导出大小、SHA 和独立复核结果以本轮新 `exports/` 回执为准。

### M1.1 R2 本次实际示例

2026-10-10 UTC 的新证据位于 `m1_1_validation/20261010T154658Z-4e5039eb-6ac2-49c7-8ece-824765e22f5f/`。对外旧 M1 示例 `exports/M1-audit-lite.zip` 为 **12,743,304 bytes**，SHA256 `0906688bcf4a9a1c6ef0a6f5ed91b9498b5a3b6c668e664283ef1d8727dc2dc3`。相对 Full Archive 逻辑字节缩减 **99.8023%**；1,516 个选中源文件对应 1,066 内容对象，其余 42,569 条为明确的 NOT_INCLUDED 指针。

`r2-m1-release-command` 真实退出 0；固定时刻的第二完整导出 `r2-release-determinism-command` 退出 0 且字节相同。`r2-offline-release-dynamic-command` 在空目录、无环境继承、Python `-I` 下使用从可信源码单独复制的 stdlib verifier，verify/inspect 各退出 0；对 README 单字节篡改的负控退出 2。另实际重新哈希 1,516 个选中原始源文件和 Full manifest，未发现源变化。没有重新哈希其余未提供的原始字节。

最终增量测试 **50/50 PASS**，包含脱敏、错误 Run、伪造 JUnit、联合削减 JUnit/report、提交树联合篡改、路径/duplicate/symlink/bomb、未停止 Run 和独立空目录核验等控制。开发中曾保留 37 PASS/1 FAIL 的选择器缺陷、首次真实导出遇到封存 `.git` binary 的拒绝，以及一次语法 collection ERROR；分别定位并修复，没有删除原始失败回执，也没有改历史成绩。第二个开发中间包尚不包含最终 required-set 字段，不是对外正式示例，留作开发证据；末次安全审查将私有路径拒绝扩展到任意深度的完整目录组件，其开发 checkpoint Gate 留存，最终状态为 `R2_GATE_FINAL.json`。

pattern redaction 不能识别任意未知秘密。导出不读取宿主真实凭据，不记录其摘要；已有 Runtime 必须在 Full Archive 进入封存前脱敏，可信宿主的最终秘密扫描继续作为门禁。明文 credential key、Bearer、常见 API-key/JWT 样式被二次脱敏；测试只使用独立假凭据。

设计复用成熟机制：[Python 官方 zipfile 文档](https://docs.python.org/3.12/library/zipfile.html) 与 [RFC 8493 BagIt manifest 思路](https://datatracker.ietf.org/doc/rfc8493/)。本 ZIP 不宣称完整 BagIt 协议兼容。

### Post-calibration verifier correction

六次Session后的独立检查定位到原生最终文本与typed父回执比较：必须保留原文whitespace、比较完整回执正文，不能单边strip或使用子串命中。Runtime parser与离线verifier分别增加严格正反控制；旧测试/原Run/旧M1 ZIP不改写。原第六轮summary的2verified保留，纠正后的第三child证明另存。当前verifier与六次挑战当时的verifier有不同SHA，不得混用版本归属。

M1.1新六Session的Audit-Lite在完整Full封存后写入外部release目录，独立验证、字节篡改、同created-at确定性和秘密扫描的实际大小/SHA/退出状态见 [M1.1 evidence index](history/orderflow/M1_1_EVIDENCE_INDEX.json)。Full与release分开封存，避免向已经sealed的Full追加最终导出receipt。
