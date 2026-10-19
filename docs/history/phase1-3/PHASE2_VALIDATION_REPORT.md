# Phase 2 Validation Report

最终结论：**PASS**

范围：Episode A 与框架扩展性验证；停止在 Phase 2。B/C/D 仍 PLANNED / NOT_IMPLEMENTED。Codex 自动接入、GraphSwarm、MCP、FalkorDB、G0–G3、Dashboard、完整支付/异步 Worker 均未实现或未运行。

Validation ID：`fb67fd4e-939b-41cd-ab60-90e14194e6e5`。全部命令为实际 subprocess，记录 UTC 时间、完整 argv、退出状态及 stdout/stderr。

[机器验收记录](runs/validation-phase2/fb67fd4e-939b-41cd-ab60-90e14194e6e5/validation.json) · [Phase 1 回归记录](runs/validation/d961a165-2bf3-46b7-9f78-4cb2ab67e176/validation.json)

## 运行环境与测试数量

- 开发者测试：107 / 107 PASS；原有 46 项另行实际执行：46 / 46 PASS。
- SMOKE-001：独立 8 项隐藏测试，正反验证、ERROR、TIMEOUT、归档、重置由 Phase 1 验收重跑。
- Episode A：独立 14 项隐藏测试，库存/数量/线程数变化、多 SKU、异常、取消/预留幂等、回滚、重置和宿主数据库对账。
- 每次主场景 200 个业务请求、200 个真实线程、一个 Worker 进程、独立 SQLite 数据库；记录 PID/thread IDs/monotonic 开始结束时间与 max_active。

## 并发实现与真实缺陷

通用 RPC batch 使用 ThreadPoolExecutor，首波 Barrier 同步入口；可选 inventory_read Event 在旧快照读取并关闭读连接后放行，最多等待 2 秒。正确修复不必调用 checkpoint；锁修复等待后放行而不死锁。Worker 不含库存答案或判分规则。
缺陷是事务前读取库存，再在事务内用过期快照绝对覆写。原 BEGIN IMMEDIATE、行非负/守恒、唯一键和 FK 全保留；这些约束不能约束跨表丢失更新。200 个请求均旧读成功时，实际订单/账本 200 条而库存 49/1，Oracle 检出 ledger_matches/order_reservations_match 冲突。
参考补丁恢复事务内条件相对 UPDATE；原 API/容量/线程入口保留。另用整段 RLock 与保留旧读取但采用条件原子 UPDATE 的提交实际运行完整 14 项，验证不限定修复策略。

## 正反与错误验收

| 提交 | Run ID | 判定 | passed / failed / errors / skipped |
|---|---|---|---|
| A-prepared-buggy | `44f75f89-5b5b-47fe-8c74-6c302ea9827e` | FAIL | 5 / 9 / 0 / 0 |
| A-reference-workspace | `d2ac2e75-d1d8-461a-8d55-fb13581f8702` | PASS | 14 / 0 / 0 / 0 |
| A-alternate-atomic | `46baa9fd-1740-4559-ab41-fc9066dca821` | PASS | 14 / 0 / 0 / 0 |
| A-alternate-lock | `b07ce31c-2038-4935-ac35-887d5b2d60cb` | PASS | 14 / 0 / 0 / 0 |
| A-syntax-error | `430c438b-4d36-448d-820b-5e84ccd880fa` | ERROR | 0 / 0 / 14 / 0 |
| A-timeout | `a6f79a51-82e1-426e-886f-9020a5b51c7c` | TIMEOUT | 0 / 0 / 0 / 0 |

独立复现器（单个受控 batch；不冒充完整 14 项 Evaluator）：

- buggy：`FAIL`，Run `cd5f5664-34a9-417f-94aa-49c0ce40e5e1`，[实际复现报告](runs/reproductions/cd5f5664-34a9-417f-94aa-49c0ce40e5e1/reproduction.json)。
- reference：`PASS`，Run `0054b4ae-318d-4329-97e9-44e8bcaf46c0`，[实际复现报告](runs/reproductions/0054b4ae-318d-4329-97e9-44e8bcaf46c0/reproduction.json)。

## 连续 10 轮独立初始化

每轮分别新建 Run UUID、候选目录和数据库，完整运行 14 项 suite；不是复用 pytest 结果或旧 DB。

| 轮次 | 提交 | Run ID | 判定 | 总数/P/F/E/S | 主场景成功/不足 | available/reserved | 线程/max_active | Oracle |
|---:|---|---|---|---|---|---|---|---|
| 1 | buggy | `eef2cf59-a630-4c00-8e03-d6319a4417d2` | FAIL | 14/5/9/0/0 | 200/0 | 49/1 | 200/200 | 账本冲突 |
| 1 | reference | `a1161fc5-c406-4658-b3cd-30803c32f8b5` | PASS | 14/14/0/0/0 | 50/150 | 0/50 | 200/200 | 一致 |
| 2 | buggy | `10b77a39-bbd9-43e2-8171-a69db7b7cc84` | FAIL | 14/5/9/0/0 | 200/0 | 49/1 | 200/200 | 账本冲突 |
| 2 | reference | `f3682256-ec87-44e7-b347-46c972f86c42` | PASS | 14/14/0/0/0 | 50/150 | 0/50 | 200/200 | 一致 |
| 3 | buggy | `0587b2d1-12d4-4e4e-a1d7-74a92ccaff48` | FAIL | 14/5/9/0/0 | 200/0 | 49/1 | 200/200 | 账本冲突 |
| 3 | reference | `91f767ab-33a2-4400-ac78-8408b11e12f3` | PASS | 14/14/0/0/0 | 50/150 | 0/50 | 200/200 | 一致 |
| 4 | buggy | `1b7feed9-7536-4977-b8c2-b801214aa858` | FAIL | 14/5/9/0/0 | 200/0 | 49/1 | 200/200 | 账本冲突 |
| 4 | reference | `d8dbb66e-9175-4528-9438-776e765e5340` | PASS | 14/14/0/0/0 | 50/150 | 0/50 | 200/200 | 一致 |
| 5 | buggy | `9b2d8d0a-c914-4618-942a-541c4002a6a2` | FAIL | 14/5/9/0/0 | 200/0 | 49/1 | 200/200 | 账本冲突 |
| 5 | reference | `987634a4-6287-4b63-af17-52759f8ddcb8` | PASS | 14/14/0/0/0 | 50/150 | 0/50 | 200/200 | 一致 |
| 6 | buggy | `e13ca865-26b2-4ed8-a05f-79d3891558f8` | FAIL | 14/5/9/0/0 | 200/0 | 49/1 | 200/200 | 账本冲突 |
| 6 | reference | `34367326-0aa9-4297-ba8d-88181166d849` | PASS | 14/14/0/0/0 | 50/150 | 0/50 | 200/200 | 一致 |
| 7 | buggy | `e7e15457-06e3-4998-a27f-4c6256fc0854` | FAIL | 14/5/9/0/0 | 200/0 | 49/1 | 200/200 | 账本冲突 |
| 7 | reference | `d710bd45-a5de-4b50-9f29-a273dbe7a3c8` | PASS | 14/14/0/0/0 | 50/150 | 0/50 | 200/200 | 一致 |
| 8 | buggy | `b148b3e5-16d7-46a1-85db-bf4c13b6074b` | FAIL | 14/5/9/0/0 | 200/0 | 49/1 | 200/200 | 账本冲突 |
| 8 | reference | `8841f6e2-91f9-463b-9316-08682354c35b` | PASS | 14/14/0/0/0 | 50/150 | 0/50 | 200/200 | 一致 |
| 9 | buggy | `82ea43a5-aead-4f50-b516-292618c55265` | FAIL | 14/5/9/0/0 | 200/0 | 49/1 | 200/200 | 账本冲突 |
| 9 | reference | `3dc55fc4-a10c-4faa-905f-972c43e62558` | PASS | 14/14/0/0/0 | 50/150 | 0/50 | 200/200 | 一致 |
| 10 | buggy | `cffa5b52-1c56-4404-845e-6ab07ea57e1f` | FAIL | 14/5/9/0/0 | 200/0 | 49/1 | 200/200 | 账本冲突 |
| 10 | reference | `a5c001fd-fd1e-45c1-9801-f4f3887807d9` | PASS | 14/14/0/0/0 | 50/150 | 0/50 | 200/200 | 一致 |

所有 buggy 主场景均须 gate arrivals=parties=200、all_arrived，实际成功 200、无锁超时；所有参考均须成功 50 / 不足 150、库存 0/50。每轮完整失败原因与证据在 validation.json 的 repeats 字段，JUnit/Oracle/batch/事件在对应 Run。
补充的无 checkpoint 压力路径不固定线程写入次序，最终判据仍是业务不变量；上表与全 suite verdict-set 稳定性检查单独验证每轮是否一致，没有忽略非确定性失败。

## 指纹与隔离

Run 保存 Submission 与实际候选 SHA256、public manifest SHA256、private manifest 文件 SHA256、Evaluator version/SHA256、Fixture version/SHA256、Suite version/SHA256、Python/SQLite/pytest/pluggy 与 bwrap/git 的实际版本及二进制 SHA256。准备前后版本改变拒绝复用；评测期间可信源码变化判 ERROR。20 轮指纹必须完全一致。
候选通过原 bubblewrap 物理挂载边界执行。A 验收实际探测 Hidden Tests、Reference Patch、Private Manifest、宿主 app、其他 Run 及 /proc/1/root 逃逸路径，并保留候选 app 存在的正控。Sandbox 无功能改动；完整隔离回归仍运行。宿主 Oracle 在 Worker 关闭后只读查询原 DB，并在独立副本上验证约束语义，不依赖 candidate audit。

## 失败记录与修复

- 开发首轮 buggy Run `f7dc4f95-86ff-4255-86a8-4390d9cf9c65`：FAIL，5/9/0/0；200 线程旧读后 SQLite 原 5 秒等待产生 96 个 OperationalError，104 个实际成功订单而库存49/1。该原始报告和堆栈保留；不是最终重复验收。
- 根据实际锁竞争将连接有界 busy timeout 改为 30 秒；复查 Run `1a1f31d2-efe4-4c10-a8e0-5362a935ef5a`：200 个业务成功、0 OperationalError，库存49/1、订单和ledger200，仍 FAIL。未改库存容量、并发度、断言或 schema。
- 初次复现器命令误填不存在的 `evaluator/reference_patches/A.diff`，Run `955ae4ac-307a-42d1-af7b-a29f47fd0db6` 实际 FileNotFoundError / ERROR / 退出2；修正为 A-v01.diff 后正反复现成功，旧错误记录保留。
- 独立审查发现 Evaluator 重用 artifacts 会混入旧 batch/Oracle，已启动前清理并加入真实 TIMEOUT 旧证据回归；发现仅数 CHECK 无法判断部分约束移除，已加入可信副本语义探针及回归。
- 上表缺陷 FAIL 为真实必要断言失败；语法错误 ERROR 和 1 秒 TIMEOUT 为独立负例。完整原始错误信息保留在每 Run 的 JUnit、pytest 日志和 execution_errors。

## 实际命令与退出状态

本机外层通过 `scripts/python312 scripts/validate_phase2.py` 使用 Python 3.12；内部完整命令如下。退出 1/2/3/4 分别代表候选 FAIL/ERROR/TIMEOUT/NOT_IMPLEMENTED，不应误读为对应候选 PASS。

### phase1-regression

UTC `2026-10-09T17:46:44.593717+00:00` → `2026-10-09T17:47:07.706359+00:00`；实际退出 `0`，预期 `0`。

```bash
<MAINTAINER_HOME>/data_storage/humble_workspace/orderflow_incident_lab/.venv/bin/python <MAINTAINER_HOME>/data_storage/humble_workspace/orderflow_incident_lab/scripts/validate_phase1.py
```

[stdout](runs/validation-phase2/fb67fd4e-939b-41cd-ab60-90e14194e6e5/01-phase1-regression.stdout.log) · [stderr](runs/validation-phase2/fb67fd4e-939b-41cd-ab60-90e14194e6e5/01-phase1-regression.stderr.log)

### original-46-tests

UTC `2026-10-09T17:47:07.708124+00:00` → `2026-10-09T17:47:14.405318+00:00`；实际退出 `0`，预期 `0`。

```bash
<MAINTAINER_HOME>/data_storage/humble_workspace/orderflow_incident_lab/.venv/bin/python -m pytest tests/test_business.py tests/test_adapters.py tests/test_framework.py tests/test_evaluator.py tests/public/test_orders.py -q --junitxml <MAINTAINER_HOME>/data_storage/humble_workspace/orderflow_incident_lab/runs/validation-phase2/fb67fd4e-939b-41cd-ab60-90e14194e6e5/original46.junit.xml
```

[stdout](runs/validation-phase2/fb67fd4e-939b-41cd-ab60-90e14194e6e5/02-original-46-tests.stdout.log) · [stderr](runs/validation-phase2/fb67fd4e-939b-41cd-ab60-90e14194e6e5/02-original-46-tests.stderr.log)

### validate-A

UTC `2026-10-09T17:47:14.407387+00:00` → `2026-10-09T17:47:14.509030+00:00`；实际退出 `0`，预期 `0`。

```bash
<MAINTAINER_HOME>/data_storage/humble_workspace/orderflow_incident_lab/.venv/bin/orderflow validate --episode A --variant v01
```

[stdout](runs/validation-phase2/fb67fd4e-939b-41cd-ab60-90e14194e6e5/03-validate-A.stdout.log) · [stderr](runs/validation-phase2/fb67fd4e-939b-41cd-ab60-90e14194e6e5/03-validate-A.stderr.log)

### prepare-A

UTC `2026-10-09T17:47:14.510480+00:00` → `2026-10-09T17:47:14.639790+00:00`；实际退出 `0`，预期 `0`。

```bash
<MAINTAINER_HOME>/data_storage/humble_workspace/orderflow_incident_lab/.venv/bin/orderflow prepare --episode A --variant v01
```

[stdout](runs/validation-phase2/fb67fd4e-939b-41cd-ab60-90e14194e6e5/04-prepare-A.stdout.log) · [stderr](runs/validation-phase2/fb67fd4e-939b-41cd-ab60-90e14194e6e5/04-prepare-A.stderr.log)

### prepare-other-smoke

UTC `2026-10-09T17:47:14.641177+00:00` → `2026-10-09T17:47:14.769706+00:00`；实际退出 `0`，预期 `0`。

```bash
<MAINTAINER_HOME>/data_storage/humble_workspace/orderflow_incident_lab/.venv/bin/orderflow prepare --episode SMOKE-001
```

[stdout](runs/validation-phase2/fb67fd4e-939b-41cd-ab60-90e14194e6e5/05-prepare-other-smoke.stdout.log) · [stderr](runs/validation-phase2/fb67fd4e-939b-41cd-ab60-90e14194e6e5/05-prepare-other-smoke.stderr.log)

### A-isolation

UTC `2026-10-09T17:47:14.770499+00:00` → `2026-10-09T17:47:14.904884+00:00`；实际退出 `0`，预期 `0`。

```bash
<MAINTAINER_HOME>/data_storage/humble_workspace/orderflow_incident_lab/.venv/bin/orderflow shell --run-id 44f75f89-5b5b-47fe-8c74-6c302ea9827e -- /usr/bin/python3.12 -I -c 'from pathlib import Path; import json; blocked=[not Path(p).exists() for p in ['"'"'<MAINTAINER_HOME>/data_storage/humble_workspace/orderflow_incident_lab/evaluator/hidden_tests'"'"', '"'"'<MAINTAINER_HOME>/data_storage/humble_workspace/orderflow_incident_lab/evaluator/reference_patches/A-v01.diff'"'"', '"'"'<MAINTAINER_HOME>/data_storage/humble_workspace/orderflow_incident_lab/evaluator/private_manifests/A.json'"'"', '"'"'<MAINTAINER_HOME>/data_storage/humble_workspace/orderflow_incident_lab/app/service.py'"'"', '"'"'<MAINTAINER_HOME>/data_storage/humble_workspace/orderflow_incident_lab/runs/b3870bd0-a88a-4162-9cf6-a289b71d092f/evaluation_report.json'"'"', '"'"'/proc/1/root<MAINTAINER_HOME>/data_storage/humble_workspace/orderflow_incident_lab/evaluator/hidden_tests'"'"', '"'"'/proc/1/root<MAINTAINER_HOME>/data_storage/humble_workspace/orderflow_incident_lab/evaluator/reference_patches/A-v01.diff'"'"', '"'"'/proc/1/root<MAINTAINER_HOME>/data_storage/humble_workspace/orderflow_incident_lab/evaluator/private_manifests/A.json'"'"', '"'"'/proc/1/root<MAINTAINER_HOME>/data_storage/humble_workspace/orderflow_incident_lab/app/service.py'"'"', '"'"'/proc/1/root<MAINTAINER_HOME>/data_storage/humble_workspace/orderflow_incident_lab/runs/b3870bd0-a88a-4162-9cf6-a289b71d092f/evaluation_report.json'"'"']]; print(json.dumps({'"'"'blocked'"'"':blocked,'"'"'candidate'"'"':Path('"'"'/workspace/app/service.py'"'"').is_file()})); assert all(blocked)'
```

[stdout](runs/validation-phase2/fb67fd4e-939b-41cd-ab60-90e14194e6e5/06-A-isolation.stdout.log) · [stderr](runs/validation-phase2/fb67fd4e-939b-41cd-ab60-90e14194e6e5/06-A-isolation.stderr.log)

### A-single-thread-public

UTC `2026-10-09T17:47:14.906552+00:00` → `2026-10-09T17:47:15.081306+00:00`；实际退出 `0`，预期 `0`。

```bash
<MAINTAINER_HOME>/data_storage/humble_workspace/orderflow_incident_lab/.venv/bin/orderflow shell --run-id 44f75f89-5b5b-47fe-8c74-6c302ea9827e -- /usr/bin/python3.12 -m unittest discover -s tests/public
```

[stdout](runs/validation-phase2/fb67fd4e-939b-41cd-ab60-90e14194e6e5/07-A-single-thread-public.stdout.log) · [stderr](runs/validation-phase2/fb67fd4e-939b-41cd-ab60-90e14194e6e5/07-A-single-thread-public.stderr.log)

### reject-episode-mix

UTC `2026-10-09T17:47:15.082249+00:00` → `2026-10-09T17:47:15.183565+00:00`；实际退出 `2`，预期 `2`。

```bash
<MAINTAINER_HOME>/data_storage/humble_workspace/orderflow_incident_lab/.venv/bin/orderflow evaluate --episode SMOKE-001 --run-id 44f75f89-5b5b-47fe-8c74-6c302ea9827e
```

[stdout](runs/validation-phase2/fb67fd4e-939b-41cd-ab60-90e14194e6e5/08-reject-episode-mix.stdout.log) · [stderr](runs/validation-phase2/fb67fd4e-939b-41cd-ab60-90e14194e6e5/08-reject-episode-mix.stderr.log)

### reject-unknown-variant

UTC `2026-10-09T17:47:15.184366+00:00` → `2026-10-09T17:47:15.285211+00:00`；实际退出 `2`，预期 `2`。

```bash
<MAINTAINER_HOME>/data_storage/humble_workspace/orderflow_incident_lab/.venv/bin/orderflow validate --episode A --variant missing
```

[stdout](runs/validation-phase2/fb67fd4e-939b-41cd-ab60-90e14194e6e5/09-reject-unknown-variant.stdout.log) · [stderr](runs/validation-phase2/fb67fd4e-939b-41cd-ab60-90e14194e6e5/09-reject-unknown-variant.stderr.log)

### A-prepared-buggy

UTC `2026-10-09T17:47:15.286473+00:00` → `2026-10-09T17:47:46.046100+00:00`；实际退出 `1`，预期 `1`。

```bash
<MAINTAINER_HOME>/data_storage/humble_workspace/orderflow_incident_lab/.venv/bin/orderflow evaluate --episode A --run-id 44f75f89-5b5b-47fe-8c74-6c302ea9827e
```

[stdout](runs/validation-phase2/fb67fd4e-939b-41cd-ab60-90e14194e6e5/10-A-prepared-buggy.stdout.log) · [stderr](runs/validation-phase2/fb67fd4e-939b-41cd-ab60-90e14194e6e5/10-A-prepared-buggy.stderr.log)

### A-reference-workspace

UTC `2026-10-09T17:47:46.051013+00:00` → `2026-10-09T17:48:02.022738+00:00`；实际退出 `0`，预期 `0`。

```bash
<MAINTAINER_HOME>/data_storage/humble_workspace/orderflow_incident_lab/.venv/bin/orderflow evaluate --episode A --submission <MAINTAINER_HOME>/data_storage/humble_workspace/orderflow_incident_lab/app
```

[stdout](runs/validation-phase2/fb67fd4e-939b-41cd-ab60-90e14194e6e5/11-A-reference-workspace.stdout.log) · [stderr](runs/validation-phase2/fb67fd4e-939b-41cd-ab60-90e14194e6e5/11-A-reference-workspace.stderr.log)

### A-alternate-atomic

UTC `2026-10-09T17:48:02.030867+00:00` → `2026-10-09T17:48:18.448177+00:00`；实际退出 `0`，预期 `0`。

```bash
<MAINTAINER_HOME>/data_storage/humble_workspace/orderflow_incident_lab/.venv/bin/orderflow evaluate --episode A --submission <MAINTAINER_HOME>/data_storage/humble_workspace/orderflow_incident_lab/runs/validation-phase2/fb67fd4e-939b-41cd-ab60-90e14194e6e5/atomic-submission
```

[stdout](runs/validation-phase2/fb67fd4e-939b-41cd-ab60-90e14194e6e5/12-A-alternate-atomic.stdout.log) · [stderr](runs/validation-phase2/fb67fd4e-939b-41cd-ab60-90e14194e6e5/12-A-alternate-atomic.stderr.log)

### A-alternate-lock

UTC `2026-10-09T17:48:18.454450+00:00` → `2026-10-09T17:48:41.644406+00:00`；实际退出 `0`，预期 `0`。

```bash
<MAINTAINER_HOME>/data_storage/humble_workspace/orderflow_incident_lab/.venv/bin/orderflow evaluate --episode A --submission <MAINTAINER_HOME>/data_storage/humble_workspace/orderflow_incident_lab/runs/validation-phase2/fb67fd4e-939b-41cd-ab60-90e14194e6e5/lock-submission
```

[stdout](runs/validation-phase2/fb67fd4e-939b-41cd-ab60-90e14194e6e5/13-A-alternate-lock.stdout.log) · [stderr](runs/validation-phase2/fb67fd4e-939b-41cd-ab60-90e14194e6e5/13-A-alternate-lock.stderr.log)

### A-syntax-error

UTC `2026-10-09T17:48:41.650212+00:00` → `2026-10-09T17:48:42.785346+00:00`；实际退出 `2`，预期 `2`。

```bash
<MAINTAINER_HOME>/data_storage/humble_workspace/orderflow_incident_lab/.venv/bin/orderflow evaluate --episode A --submission <MAINTAINER_HOME>/data_storage/humble_workspace/orderflow_incident_lab/runs/validation-phase2/fb67fd4e-939b-41cd-ab60-90e14194e6e5/syntax-submission
```

[stdout](runs/validation-phase2/fb67fd4e-939b-41cd-ab60-90e14194e6e5/14-A-syntax-error.stdout.log) · [stderr](runs/validation-phase2/fb67fd4e-939b-41cd-ab60-90e14194e6e5/14-A-syntax-error.stderr.log)

### A-timeout

UTC `2026-10-09T17:48:42.787800+00:00` → `2026-10-09T17:48:43.955673+00:00`；实际退出 `3`，预期 `3`。

```bash
<MAINTAINER_HOME>/data_storage/humble_workspace/orderflow_incident_lab/.venv/bin/orderflow evaluate --episode A --submission <MAINTAINER_HOME>/data_storage/humble_workspace/orderflow_incident_lab/runs/validation-phase2/fb67fd4e-939b-41cd-ab60-90e14194e6e5/timeout-submission --timeout 1
```

[stdout](runs/validation-phase2/fb67fd4e-939b-41cd-ab60-90e14194e6e5/15-A-timeout.stdout.log) · [stderr](runs/validation-phase2/fb67fd4e-939b-41cd-ab60-90e14194e6e5/15-A-timeout.stderr.log)

### reproducer-buggy

UTC `2026-10-09T17:48:43.957142+00:00` → `2026-10-09T17:49:00.928450+00:00`；实际退出 `1`，预期 `1`。

```bash
<MAINTAINER_HOME>/data_storage/humble_workspace/orderflow_incident_lab/.venv/bin/python <MAINTAINER_HOME>/data_storage/humble_workspace/orderflow_incident_lab/scripts/reproduce_episode_a.py
```

[stdout](runs/validation-phase2/fb67fd4e-939b-41cd-ab60-90e14194e6e5/16-reproducer-buggy.stdout.log) · [stderr](runs/validation-phase2/fb67fd4e-939b-41cd-ab60-90e14194e6e5/16-reproducer-buggy.stderr.log)

### reproducer-reference

UTC `2026-10-09T17:49:00.929926+00:00` → `2026-10-09T17:49:05.428927+00:00`；实际退出 `0`，预期 `0`。

```bash
<MAINTAINER_HOME>/data_storage/humble_workspace/orderflow_incident_lab/.venv/bin/python <MAINTAINER_HOME>/data_storage/humble_workspace/orderflow_incident_lab/scripts/reproduce_episode_a.py --submission <MAINTAINER_HOME>/data_storage/humble_workspace/orderflow_incident_lab/evaluator/reference_patches/A-v01.diff
```

[stdout](runs/validation-phase2/fb67fd4e-939b-41cd-ab60-90e14194e6e5/17-reproducer-reference.stdout.log) · [stderr](runs/validation-phase2/fb67fd4e-939b-41cd-ab60-90e14194e6e5/17-reproducer-reference.stderr.log)

### repeat-01-buggy

UTC `2026-10-09T17:49:05.430495+00:00` → `2026-10-09T17:49:38.022053+00:00`；实际退出 `1`，预期 `1`。

```bash
<MAINTAINER_HOME>/data_storage/humble_workspace/orderflow_incident_lab/.venv/bin/orderflow evaluate --episode A
```

[stdout](runs/validation-phase2/fb67fd4e-939b-41cd-ab60-90e14194e6e5/18-repeat-01-buggy.stdout.log) · [stderr](runs/validation-phase2/fb67fd4e-939b-41cd-ab60-90e14194e6e5/18-repeat-01-buggy.stderr.log)

### repeat-01-reference

UTC `2026-10-09T17:49:38.030612+00:00` → `2026-10-09T17:49:55.819197+00:00`；实际退出 `0`，预期 `0`。

```bash
<MAINTAINER_HOME>/data_storage/humble_workspace/orderflow_incident_lab/.venv/bin/orderflow evaluate --episode A --submission <MAINTAINER_HOME>/data_storage/humble_workspace/orderflow_incident_lab/evaluator/reference_patches/A-v01.diff
```

[stdout](runs/validation-phase2/fb67fd4e-939b-41cd-ab60-90e14194e6e5/19-repeat-01-reference.stdout.log) · [stderr](runs/validation-phase2/fb67fd4e-939b-41cd-ab60-90e14194e6e5/19-repeat-01-reference.stderr.log)

### repeat-02-buggy

UTC `2026-10-09T17:49:55.827036+00:00` → `2026-10-09T17:50:28.779973+00:00`；实际退出 `1`，预期 `1`。

```bash
<MAINTAINER_HOME>/data_storage/humble_workspace/orderflow_incident_lab/.venv/bin/orderflow evaluate --episode A
```

[stdout](runs/validation-phase2/fb67fd4e-939b-41cd-ab60-90e14194e6e5/20-repeat-02-buggy.stdout.log) · [stderr](runs/validation-phase2/fb67fd4e-939b-41cd-ab60-90e14194e6e5/20-repeat-02-buggy.stderr.log)

### repeat-02-reference

UTC `2026-10-09T17:50:28.791816+00:00` → `2026-10-09T17:50:45.736065+00:00`；实际退出 `0`，预期 `0`。

```bash
<MAINTAINER_HOME>/data_storage/humble_workspace/orderflow_incident_lab/.venv/bin/orderflow evaluate --episode A --submission <MAINTAINER_HOME>/data_storage/humble_workspace/orderflow_incident_lab/evaluator/reference_patches/A-v01.diff
```

[stdout](runs/validation-phase2/fb67fd4e-939b-41cd-ab60-90e14194e6e5/21-repeat-02-reference.stdout.log) · [stderr](runs/validation-phase2/fb67fd4e-939b-41cd-ab60-90e14194e6e5/21-repeat-02-reference.stderr.log)

### repeat-03-buggy

UTC `2026-10-09T17:50:45.745707+00:00` → `2026-10-09T17:51:16.016876+00:00`；实际退出 `1`，预期 `1`。

```bash
<MAINTAINER_HOME>/data_storage/humble_workspace/orderflow_incident_lab/.venv/bin/orderflow evaluate --episode A
```

[stdout](runs/validation-phase2/fb67fd4e-939b-41cd-ab60-90e14194e6e5/22-repeat-03-buggy.stdout.log) · [stderr](runs/validation-phase2/fb67fd4e-939b-41cd-ab60-90e14194e6e5/22-repeat-03-buggy.stderr.log)

### repeat-03-reference

UTC `2026-10-09T17:51:16.029880+00:00` → `2026-10-09T17:51:32.122278+00:00`；实际退出 `0`，预期 `0`。

```bash
<MAINTAINER_HOME>/data_storage/humble_workspace/orderflow_incident_lab/.venv/bin/orderflow evaluate --episode A --submission <MAINTAINER_HOME>/data_storage/humble_workspace/orderflow_incident_lab/evaluator/reference_patches/A-v01.diff
```

[stdout](runs/validation-phase2/fb67fd4e-939b-41cd-ab60-90e14194e6e5/23-repeat-03-reference.stdout.log) · [stderr](runs/validation-phase2/fb67fd4e-939b-41cd-ab60-90e14194e6e5/23-repeat-03-reference.stderr.log)

### repeat-04-buggy

UTC `2026-10-09T17:51:32.133770+00:00` → `2026-10-09T17:52:05.448719+00:00`；实际退出 `1`，预期 `1`。

```bash
<MAINTAINER_HOME>/data_storage/humble_workspace/orderflow_incident_lab/.venv/bin/orderflow evaluate --episode A
```

[stdout](runs/validation-phase2/fb67fd4e-939b-41cd-ab60-90e14194e6e5/24-repeat-04-buggy.stdout.log) · [stderr](runs/validation-phase2/fb67fd4e-939b-41cd-ab60-90e14194e6e5/24-repeat-04-buggy.stderr.log)

### repeat-04-reference

UTC `2026-10-09T17:52:05.462691+00:00` → `2026-10-09T17:52:21.815508+00:00`；实际退出 `0`，预期 `0`。

```bash
<MAINTAINER_HOME>/data_storage/humble_workspace/orderflow_incident_lab/.venv/bin/orderflow evaluate --episode A --submission <MAINTAINER_HOME>/data_storage/humble_workspace/orderflow_incident_lab/evaluator/reference_patches/A-v01.diff
```

[stdout](runs/validation-phase2/fb67fd4e-939b-41cd-ab60-90e14194e6e5/25-repeat-04-reference.stdout.log) · [stderr](runs/validation-phase2/fb67fd4e-939b-41cd-ab60-90e14194e6e5/25-repeat-04-reference.stderr.log)

### repeat-05-buggy

UTC `2026-10-09T17:52:21.828847+00:00` → `2026-10-09T17:52:55.218150+00:00`；实际退出 `1`，预期 `1`。

```bash
<MAINTAINER_HOME>/data_storage/humble_workspace/orderflow_incident_lab/.venv/bin/orderflow evaluate --episode A
```

[stdout](runs/validation-phase2/fb67fd4e-939b-41cd-ab60-90e14194e6e5/26-repeat-05-buggy.stdout.log) · [stderr](runs/validation-phase2/fb67fd4e-939b-41cd-ab60-90e14194e6e5/26-repeat-05-buggy.stderr.log)

### repeat-05-reference

UTC `2026-10-09T17:52:55.233842+00:00` → `2026-10-09T17:53:11.588978+00:00`；实际退出 `0`，预期 `0`。

```bash
<MAINTAINER_HOME>/data_storage/humble_workspace/orderflow_incident_lab/.venv/bin/orderflow evaluate --episode A --submission <MAINTAINER_HOME>/data_storage/humble_workspace/orderflow_incident_lab/evaluator/reference_patches/A-v01.diff
```

[stdout](runs/validation-phase2/fb67fd4e-939b-41cd-ab60-90e14194e6e5/27-repeat-05-reference.stdout.log) · [stderr](runs/validation-phase2/fb67fd4e-939b-41cd-ab60-90e14194e6e5/27-repeat-05-reference.stderr.log)

### repeat-06-buggy

UTC `2026-10-09T17:53:11.604427+00:00` → `2026-10-09T17:53:44.298580+00:00`；实际退出 `1`，预期 `1`。

```bash
<MAINTAINER_HOME>/data_storage/humble_workspace/orderflow_incident_lab/.venv/bin/orderflow evaluate --episode A
```

[stdout](runs/validation-phase2/fb67fd4e-939b-41cd-ab60-90e14194e6e5/28-repeat-06-buggy.stdout.log) · [stderr](runs/validation-phase2/fb67fd4e-939b-41cd-ab60-90e14194e6e5/28-repeat-06-buggy.stderr.log)

### repeat-06-reference

UTC `2026-10-09T17:53:44.319168+00:00` → `2026-10-09T17:54:00.442176+00:00`；实际退出 `0`，预期 `0`。

```bash
<MAINTAINER_HOME>/data_storage/humble_workspace/orderflow_incident_lab/.venv/bin/orderflow evaluate --episode A --submission <MAINTAINER_HOME>/data_storage/humble_workspace/orderflow_incident_lab/evaluator/reference_patches/A-v01.diff
```

[stdout](runs/validation-phase2/fb67fd4e-939b-41cd-ab60-90e14194e6e5/29-repeat-06-reference.stdout.log) · [stderr](runs/validation-phase2/fb67fd4e-939b-41cd-ab60-90e14194e6e5/29-repeat-06-reference.stderr.log)

### repeat-07-buggy

UTC `2026-10-09T17:54:00.460467+00:00` → `2026-10-09T17:54:31.243755+00:00`；实际退出 `1`，预期 `1`。

```bash
<MAINTAINER_HOME>/data_storage/humble_workspace/orderflow_incident_lab/.venv/bin/orderflow evaluate --episode A
```

[stdout](runs/validation-phase2/fb67fd4e-939b-41cd-ab60-90e14194e6e5/30-repeat-07-buggy.stdout.log) · [stderr](runs/validation-phase2/fb67fd4e-939b-41cd-ab60-90e14194e6e5/30-repeat-07-buggy.stderr.log)

### repeat-07-reference

UTC `2026-10-09T17:54:31.262952+00:00` → `2026-10-09T17:54:48.690114+00:00`；实际退出 `0`，预期 `0`。

```bash
<MAINTAINER_HOME>/data_storage/humble_workspace/orderflow_incident_lab/.venv/bin/orderflow evaluate --episode A --submission <MAINTAINER_HOME>/data_storage/humble_workspace/orderflow_incident_lab/evaluator/reference_patches/A-v01.diff
```

[stdout](runs/validation-phase2/fb67fd4e-939b-41cd-ab60-90e14194e6e5/31-repeat-07-reference.stdout.log) · [stderr](runs/validation-phase2/fb67fd4e-939b-41cd-ab60-90e14194e6e5/31-repeat-07-reference.stderr.log)

### repeat-08-buggy

UTC `2026-10-09T17:54:48.708742+00:00` → `2026-10-09T17:55:18.690774+00:00`；实际退出 `1`，预期 `1`。

```bash
<MAINTAINER_HOME>/data_storage/humble_workspace/orderflow_incident_lab/.venv/bin/orderflow evaluate --episode A
```

[stdout](runs/validation-phase2/fb67fd4e-939b-41cd-ab60-90e14194e6e5/32-repeat-08-buggy.stdout.log) · [stderr](runs/validation-phase2/fb67fd4e-939b-41cd-ab60-90e14194e6e5/32-repeat-08-buggy.stderr.log)

### repeat-08-reference

UTC `2026-10-09T17:55:18.711901+00:00` → `2026-10-09T17:55:33.989652+00:00`；实际退出 `0`，预期 `0`。

```bash
<MAINTAINER_HOME>/data_storage/humble_workspace/orderflow_incident_lab/.venv/bin/orderflow evaluate --episode A --submission <MAINTAINER_HOME>/data_storage/humble_workspace/orderflow_incident_lab/evaluator/reference_patches/A-v01.diff
```

[stdout](runs/validation-phase2/fb67fd4e-939b-41cd-ab60-90e14194e6e5/33-repeat-08-reference.stdout.log) · [stderr](runs/validation-phase2/fb67fd4e-939b-41cd-ab60-90e14194e6e5/33-repeat-08-reference.stderr.log)

### repeat-09-buggy

UTC `2026-10-09T17:55:34.010063+00:00` → `2026-10-09T17:56:04.031957+00:00`；实际退出 `1`，预期 `1`。

```bash
<MAINTAINER_HOME>/data_storage/humble_workspace/orderflow_incident_lab/.venv/bin/orderflow evaluate --episode A
```

[stdout](runs/validation-phase2/fb67fd4e-939b-41cd-ab60-90e14194e6e5/34-repeat-09-buggy.stdout.log) · [stderr](runs/validation-phase2/fb67fd4e-939b-41cd-ab60-90e14194e6e5/34-repeat-09-buggy.stderr.log)

### repeat-09-reference

UTC `2026-10-09T17:56:04.058512+00:00` → `2026-10-09T17:56:19.837109+00:00`；实际退出 `0`，预期 `0`。

```bash
<MAINTAINER_HOME>/data_storage/humble_workspace/orderflow_incident_lab/.venv/bin/orderflow evaluate --episode A --submission <MAINTAINER_HOME>/data_storage/humble_workspace/orderflow_incident_lab/evaluator/reference_patches/A-v01.diff
```

[stdout](runs/validation-phase2/fb67fd4e-939b-41cd-ab60-90e14194e6e5/35-repeat-09-reference.stdout.log) · [stderr](runs/validation-phase2/fb67fd4e-939b-41cd-ab60-90e14194e6e5/35-repeat-09-reference.stderr.log)

### repeat-10-buggy

UTC `2026-10-09T17:56:19.863452+00:00` → `2026-10-09T17:56:50.739712+00:00`；实际退出 `1`，预期 `1`。

```bash
<MAINTAINER_HOME>/data_storage/humble_workspace/orderflow_incident_lab/.venv/bin/orderflow evaluate --episode A
```

[stdout](runs/validation-phase2/fb67fd4e-939b-41cd-ab60-90e14194e6e5/36-repeat-10-buggy.stdout.log) · [stderr](runs/validation-phase2/fb67fd4e-939b-41cd-ab60-90e14194e6e5/36-repeat-10-buggy.stderr.log)

### repeat-10-reference

UTC `2026-10-09T17:56:50.767646+00:00` → `2026-10-09T17:57:07.491726+00:00`；实际退出 `0`，预期 `0`。

```bash
<MAINTAINER_HOME>/data_storage/humble_workspace/orderflow_incident_lab/.venv/bin/orderflow evaluate --episode A --submission <MAINTAINER_HOME>/data_storage/humble_workspace/orderflow_incident_lab/evaluator/reference_patches/A-v01.diff
```

[stdout](runs/validation-phase2/fb67fd4e-939b-41cd-ab60-90e14194e6e5/37-repeat-10-reference.stdout.log) · [stderr](runs/validation-phase2/fb67fd4e-939b-41cd-ab60-90e14194e6e5/37-repeat-10-reference.stderr.log)

### A-report-query

UTC `2026-10-09T17:57:07.529779+00:00` → `2026-10-09T17:57:07.653385+00:00`；实际退出 `0`，预期 `0`。

```bash
<MAINTAINER_HOME>/data_storage/humble_workspace/orderflow_incident_lab/.venv/bin/orderflow report --run-id a5c001fd-fd1e-45c1-9801-f4f3887807d9
```

[stdout](runs/validation-phase2/fb67fd4e-939b-41cd-ab60-90e14194e6e5/38-A-report-query.stdout.log) · [stderr](runs/validation-phase2/fb67fd4e-939b-41cd-ab60-90e14194e6e5/38-A-report-query.stderr.log)

### A-explicit-reset

UTC `2026-10-09T17:57:07.664014+00:00` → `2026-10-09T17:57:08.091680+00:00`；实际退出 `0`，预期 `0`。

```bash
<MAINTAINER_HOME>/data_storage/humble_workspace/orderflow_incident_lab/.venv/bin/orderflow reset --episode A
```

[stdout](runs/validation-phase2/fb67fd4e-939b-41cd-ab60-90e14194e6e5/39-A-explicit-reset.stdout.log) · [stderr](runs/validation-phase2/fb67fd4e-939b-41cd-ab60-90e14194e6e5/39-A-explicit-reset.stderr.log)

## 本次实际版本与摘要

Python：`3.12.13 (main, Nov 10 2011, 15:00:00) [GCC 14.3.0]`；SQLite：`3.46.1`；pytest：`9.1.1`；pluggy：`1.6.0`。
平台：`Linux-6.8.0-138-generic-x86_64-with-glibc2.40`；`bubblewrap 0.6.1`；`git version 2.34.1`。

| 指纹 | 真实 SHA256 |
|---|---|
| evaluator / 2.0.0 | `8a854652ec98a894783e31eadc60b2e3855170d3fdc09f73d2d7d4c3a78a5ce7` |
| fixture / 1.0.0 | `345f255ba3559023c134e4152a90483ce11427a501e6626b9126b08fb0ff90f9` |
| test_suite / 1.0.0 | `7b0b6b0c7ae168ea32b0d93eb46109aec385d48a95c8f5cab029c84300d1aa97` |
| A private manifest | `cf26a8b552c4f2cc7acdd4045cd7daf4f0f6526b29ef02c010a1af662977ad7d` |

各源码摘要的逐文件清单、Python/git/bwrap 二进制摘要与每 Run 提交摘要保存在实际 JSON Report 中；20 轮上述完整指纹相同。

## 逐项验收

| 检查 | 结果 |
|---|---|
| Phase 1 acceptance commands and checks all pass | PASS |
| Full developer tests have no failures/errors/skips | PASS |
| All original 46 developer tests still run and pass | PASS |
| Original test identities are retained in full suite | PASS |
| A manifest ready through CLI | PASS |
| A independent fixture prepared | PASS |
| Hidden/reference/private/host/other runs and proc escape inaccessible | PASS |
| Prepared buggy receives actual FAIL | PASS |
| Correct workspace submission PASS | PASS |
| atomic alternate full suite PASS with real threaded ingress | PASS |
| lock alternate full suite PASS with real threaded ingress | PASS |
| A candidate exception is ERROR not PASS | PASS |
| A evaluator deadline yields TIMEOUT | PASS |
| Reproducer buggy executes real batch with independent Oracle | PASS |
| Reproducer reference executes real batch with independent Oracle | PASS |
| repeat-01-buggy complete suite, no skipped or infrastructure errors | PASS |
| repeat-01-buggy one process with 200 real concurrent threads | PASS |
| repeat-01-buggy controlled lost-update FAIL | PASS |
| repeat-01-buggy environment independently reset | PASS |
| repeat-01-reference complete suite, no skipped or infrastructure errors | PASS |
| repeat-01-reference one process with 200 real concurrent threads | PASS |
| repeat-01-reference reference PASS with independent accounting | PASS |
| repeat-01-reference environment independently reset | PASS |
| repeat-02-buggy complete suite, no skipped or infrastructure errors | PASS |
| repeat-02-buggy one process with 200 real concurrent threads | PASS |
| repeat-02-buggy controlled lost-update FAIL | PASS |
| repeat-02-buggy environment independently reset | PASS |
| repeat-02-reference complete suite, no skipped or infrastructure errors | PASS |
| repeat-02-reference one process with 200 real concurrent threads | PASS |
| repeat-02-reference reference PASS with independent accounting | PASS |
| repeat-02-reference environment independently reset | PASS |
| repeat-03-buggy complete suite, no skipped or infrastructure errors | PASS |
| repeat-03-buggy one process with 200 real concurrent threads | PASS |
| repeat-03-buggy controlled lost-update FAIL | PASS |
| repeat-03-buggy environment independently reset | PASS |
| repeat-03-reference complete suite, no skipped or infrastructure errors | PASS |
| repeat-03-reference one process with 200 real concurrent threads | PASS |
| repeat-03-reference reference PASS with independent accounting | PASS |
| repeat-03-reference environment independently reset | PASS |
| repeat-04-buggy complete suite, no skipped or infrastructure errors | PASS |
| repeat-04-buggy one process with 200 real concurrent threads | PASS |
| repeat-04-buggy controlled lost-update FAIL | PASS |
| repeat-04-buggy environment independently reset | PASS |
| repeat-04-reference complete suite, no skipped or infrastructure errors | PASS |
| repeat-04-reference one process with 200 real concurrent threads | PASS |
| repeat-04-reference reference PASS with independent accounting | PASS |
| repeat-04-reference environment independently reset | PASS |
| repeat-05-buggy complete suite, no skipped or infrastructure errors | PASS |
| repeat-05-buggy one process with 200 real concurrent threads | PASS |
| repeat-05-buggy controlled lost-update FAIL | PASS |
| repeat-05-buggy environment independently reset | PASS |
| repeat-05-reference complete suite, no skipped or infrastructure errors | PASS |
| repeat-05-reference one process with 200 real concurrent threads | PASS |
| repeat-05-reference reference PASS with independent accounting | PASS |
| repeat-05-reference environment independently reset | PASS |
| repeat-06-buggy complete suite, no skipped or infrastructure errors | PASS |
| repeat-06-buggy one process with 200 real concurrent threads | PASS |
| repeat-06-buggy controlled lost-update FAIL | PASS |
| repeat-06-buggy environment independently reset | PASS |
| repeat-06-reference complete suite, no skipped or infrastructure errors | PASS |
| repeat-06-reference one process with 200 real concurrent threads | PASS |
| repeat-06-reference reference PASS with independent accounting | PASS |
| repeat-06-reference environment independently reset | PASS |
| repeat-07-buggy complete suite, no skipped or infrastructure errors | PASS |
| repeat-07-buggy one process with 200 real concurrent threads | PASS |
| repeat-07-buggy controlled lost-update FAIL | PASS |
| repeat-07-buggy environment independently reset | PASS |
| repeat-07-reference complete suite, no skipped or infrastructure errors | PASS |
| repeat-07-reference one process with 200 real concurrent threads | PASS |
| repeat-07-reference reference PASS with independent accounting | PASS |
| repeat-07-reference environment independently reset | PASS |
| repeat-08-buggy complete suite, no skipped or infrastructure errors | PASS |
| repeat-08-buggy one process with 200 real concurrent threads | PASS |
| repeat-08-buggy controlled lost-update FAIL | PASS |
| repeat-08-buggy environment independently reset | PASS |
| repeat-08-reference complete suite, no skipped or infrastructure errors | PASS |
| repeat-08-reference one process with 200 real concurrent threads | PASS |
| repeat-08-reference reference PASS with independent accounting | PASS |
| repeat-08-reference environment independently reset | PASS |
| repeat-09-buggy complete suite, no skipped or infrastructure errors | PASS |
| repeat-09-buggy one process with 200 real concurrent threads | PASS |
| repeat-09-buggy controlled lost-update FAIL | PASS |
| repeat-09-buggy environment independently reset | PASS |
| repeat-09-reference complete suite, no skipped or infrastructure errors | PASS |
| repeat-09-reference one process with 200 real concurrent threads | PASS |
| repeat-09-reference reference PASS with independent accounting | PASS |
| repeat-09-reference environment independently reset | PASS |
| repeat-10-buggy complete suite, no skipped or infrastructure errors | PASS |
| repeat-10-buggy one process with 200 real concurrent threads | PASS |
| repeat-10-buggy controlled lost-update FAIL | PASS |
| repeat-10-buggy environment independently reset | PASS |
| repeat-10-reference complete suite, no skipped or infrastructure errors | PASS |
| repeat-10-reference one process with 200 real concurrent threads | PASS |
| repeat-10-reference reference PASS with independent accounting | PASS |
| repeat-10-reference environment independently reset | PASS |
| Twenty unique independent run IDs | PASS |
| Repeat evaluator/private/fixture/suite/environment fingerprints identical | PASS |
| buggy full test verdict set stable across ten runs | PASS |
| reference full test verdict set stable across ten runs | PASS |
| Report read equals archived final result | PASS |
| A reset isolated from Smoke | PASS |
| A-prepared-buggy archived JSON and events | PASS |
| A-prepared-buggy no invented Agent or experience observations | PASS |
| A-reference-workspace archived JSON and events | PASS |
| A-reference-workspace no invented Agent or experience observations | PASS |
| A-alternate-atomic archived JSON and events | PASS |
| A-alternate-atomic no invented Agent or experience observations | PASS |
| A-alternate-lock archived JSON and events | PASS |
| A-alternate-lock no invented Agent or experience observations | PASS |
| A-syntax-error archived JSON and events | PASS |
| A-syntax-error no invented Agent or experience observations | PASS |
| A-timeout archived JSON and events | PASS |
| A-timeout no invented Agent or experience observations | PASS |
| repeat-01-buggy archived JSON and events | PASS |
| repeat-01-buggy no invented Agent or experience observations | PASS |
| repeat-01-reference archived JSON and events | PASS |
| repeat-01-reference no invented Agent or experience observations | PASS |
| repeat-02-buggy archived JSON and events | PASS |
| repeat-02-buggy no invented Agent or experience observations | PASS |
| repeat-02-reference archived JSON and events | PASS |
| repeat-02-reference no invented Agent or experience observations | PASS |
| repeat-03-buggy archived JSON and events | PASS |
| repeat-03-buggy no invented Agent or experience observations | PASS |
| repeat-03-reference archived JSON and events | PASS |
| repeat-03-reference no invented Agent or experience observations | PASS |
| repeat-04-buggy archived JSON and events | PASS |
| repeat-04-buggy no invented Agent or experience observations | PASS |
| repeat-04-reference archived JSON and events | PASS |
| repeat-04-reference no invented Agent or experience observations | PASS |
| repeat-05-buggy archived JSON and events | PASS |
| repeat-05-buggy no invented Agent or experience observations | PASS |
| repeat-05-reference archived JSON and events | PASS |
| repeat-05-reference no invented Agent or experience observations | PASS |
| repeat-06-buggy archived JSON and events | PASS |
| repeat-06-buggy no invented Agent or experience observations | PASS |
| repeat-06-reference archived JSON and events | PASS |
| repeat-06-reference no invented Agent or experience observations | PASS |
| repeat-07-buggy archived JSON and events | PASS |
| repeat-07-buggy no invented Agent or experience observations | PASS |
| repeat-07-reference archived JSON and events | PASS |
| repeat-07-reference no invented Agent or experience observations | PASS |
| repeat-08-buggy archived JSON and events | PASS |
| repeat-08-buggy no invented Agent or experience observations | PASS |
| repeat-08-reference archived JSON and events | PASS |
| repeat-08-reference no invented Agent or experience observations | PASS |
| repeat-09-buggy archived JSON and events | PASS |
| repeat-09-buggy no invented Agent or experience observations | PASS |
| repeat-09-reference archived JSON and events | PASS |
| repeat-09-reference no invented Agent or experience observations | PASS |
| repeat-10-buggy archived JSON and events | PASS |
| repeat-10-buggy no invented Agent or experience observations | PASS |
| repeat-10-reference archived JSON and events | PASS |
| repeat-10-reference no invented Agent or experience observations | PASS |

## 已知限制与下一阶段接口

- 仅验证单进程、多线程、文件 SQLite 拓扑。多进程、多机、网络隔离、CPU/内存/seccomp 限制、敌对 RPC/反作弊与任意恶意 SQLite 文件防御不是本轮完成项。30 秒等待有边界，超出竞争能力仍由异常/超时判失败。
- 场景正式故障 variant 仅 v01/stale-snapshot；多组参数与时序测试不宣称已实现新的正式 Episode。
- Agent adapter 仍 manual，原生 Codex 自动启动/委派/trace 不可用；Experience adapter 四接口 Disabled，无经验命中、决策或反馈。
- 后续 Episode 通过 registry/factory/private suite 接入，Runner 生命周期不改；Payment/Event 契约与经验接口留给后续阶段。
- 源码、补丁、batch/Oracle、JUnit、报告和真实版本指纹提供未来经验产生的证据；本轮没有运行 Decision Trace、Experience Retrieval 或 Feedback Evolution。

## 交付复核

[delivery-check.json](runs/validation-phase2/fb67fd4e-939b-41cd-ab60-90e14194e6e5/delivery-check.json) 记录了验收后的实际只读核对：当前可信源码指纹与最终 20 次 Run 一致；各 Run 的 JUnit 与 JSON Report 完全对应；临时评测数据库目录已移除；文档本地链接均存在；无存活候选 Worker。

最终验收：**PASS**。停止在 Phase 2，等待下一轮架构审查。
