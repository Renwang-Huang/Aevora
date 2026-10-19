# Phase 1 Validation Report

验收结论：**PASS**

范围：Phase 1 回归验收（Phase 2 源码）。A 已接入；其完整验收另见 PHASE2_VALIDATION_REPORT.md。B/C/D、Codex 自动运行、GraphSwarm 和 G0–G3 未实现或未运行。

Validation ID：`d961a165-2bf3-46b7-9f78-4cb2ab67e176`。命令均在项目根目录的实际 Python 3.12 环境执行；UTC 时间、argv、stdout/stderr 与退出状态来自 subprocess。

完整机器记录：[validation.json](runs/validation/d961a165-2bf3-46b7-9f78-4cb2ab67e176/validation.json)

## 实际命令与退出状态

退出 1/2/3/4 是针对缺陷、错误、超时、未实现的预期结果，不能当作对应任务 PASS。

| 步骤 | 实际退出 | 预期退出 | 匹配 |
|---|---:|---:|---|
| dependency-install | 0 | 0 | 是 |
| dependency-check | 0 | 0 | 是 |
| runtime | 0 | 0 | 是 |
| framework-tests | 0 | 0 | 是 |
| episode-list | 0 | 0 | 是 |
| validate-smoke | 0 | 0 | 是 |
| business-path | 0 | 0 | 是 |
| prepare-smoke | 0 | 0 | 是 |
| file-isolation | 0 | 0 | 是 |
| public-smoke | 0 | 0 | 是 |
| actual-defect-path | 0 | 0 | 是 |
| buggy-evaluation | 1 | 1 | 是 |
| reference-patch | 0 | 0 | 是 |
| reference-workspace | 0 | 0 | 是 |
| report-query | 0 | 0 | 是 |
| reset-smoke | 0 | 0 | 是 |
| buggy-repeat | 1 | 1 | 是 |
| reference-repeat | 0 | 0 | 是 |
| validate-implemented-A | 0 | 0 | 是 |
| validate-planned-B | 4 | 4 | 是 |
| evaluate-planned-B | 4 | 4 | 是 |
| validate-planned-C | 4 | 4 | 是 |
| evaluate-planned-C | 4 | 4 | 是 |
| validate-planned-D | 4 | 4 | 是 |
| evaluate-planned-D | 4 | 4 | 是 |
| syntax-error | 2 | 2 | 是 |
| timeout | 3 | 3 | 是 |
| invalid-submission | 2 | 2 | 是 |

## 真实测试与执行结果

| 提交/场景 | Run ID | 判定 | passed / failed / errors / skipped |
|---|---|---|---|
| buggy | `1b748db5-2da1-4f12-bc0c-5309ac794027` | FAIL | 0 / 8 / 0 / 0 |
| reference-patch | `a8e532fa-a638-4c58-88f4-fb8896f14213` | PASS | 8 / 0 / 0 / 0 |
| reference-workspace | `9eb8ad04-801f-4209-a0d6-b04833aac55e` | PASS | 8 / 0 / 0 / 0 |
| buggy-repeat | `1293d581-3236-42c7-bcb1-d498b2d15493` | FAIL | 0 / 8 / 0 / 0 |
| reference-repeat | `fc523c51-f150-48f2-b5f5-6e5f7cf33955` | PASS | 8 / 0 / 0 / 0 |
| planned-B | `73566960-8328-4faf-b294-9bbb8172f5b6` | NOT_IMPLEMENTED | 未执行 |
| planned-C | `2632450f-7977-4133-a8de-d4b00922118a` | NOT_IMPLEMENTED | 未执行 |
| planned-D | `ec04dacd-00d9-4c8a-bb9d-1f497668f0ea` | NOT_IMPLEMENTED | 未执行 |
| syntax-error | `704b04e8-7826-448f-8f19-6373007d862d` | ERROR | 0 / 0 / 8 / 0 |
| timeout | `e73d9ec5-3b71-4500-a7b4-7bbfa7b76ede` | TIMEOUT | 0 / 0 / 0 / 0 |
| invalid-submission | `324deec5-b68d-4ac2-976d-8b36d8136ad2` | ERROR | 未执行 |

完整开发者测试 stdout：

```text
........................................................................ [ 67%]
...................................                                      [100%]
107 passed in 10.08s
```

## 失败记录

- 缺陷提交真实出现重复释放，库存序列为 `10 → 7 → 10 → 13`；两次独立 oracle 均 FAIL，原始断言/堆栈保存在对应 Run 的 JUnit 和 pytest 日志。
- 语法错误提交的独立 worker 初始化失败，判定 ERROR；挂起提交达到 1 秒截止，判定 TIMEOUT；不存在的 patch 被拒绝并记录实际路径及事件。
- B/C/D 均 PLANNED / NOT_IMPLEMENTED；无隐藏测试调用、无 PASS 记录。A 的 readiness 已检查为 READY，其实际并发验收单独记录。
- 开发环境最初 `uv python install 3.12` 退出 1：下载域名 DNS 失败。该历史结果来自开发工具输出；验收采用本机 Flatpak Python 3.12.13 与离线依赖快照，实际重新安装及 pip check 见上表。
- 独立审查发现 DB reset 跟随符号链接与临时 DB 清理路径问题，已修复并加入完整开发者回归；没有删除或放宽失败断言。

## 验收检查

| 检查 | 结果 |
|---|---|
| A implemented and B/C/D still PLANNED | PASS |
| Scenario Manifest valid and SMOKE ready | PASS |
| Real business database and cancellation path | PASS |
| Runner loads and prepares SMOKE-001 | PASS |
| Agent sandbox cannot read hidden/reference/host baseline | PASS |
| Defective implementation really releases stock twice | PASS |
| JSON report query returns archived result | PASS |
| Environment explicitly reset | PASS |
| reference-patch actually passes all hidden tests | PASS |
| reference-workspace actually passes all hidden tests | PASS |
| reference-repeat actually passes all hidden tests | PASS |
| buggy actually fails hidden assertions | PASS |
| buggy-repeat actually fails hidden assertions | PASS |
| Defect reproducible after reset | PASS |
| Reference reproducible after reset | PASS |
| A readiness updated without conflating PLANNED Episodes | PASS |
| B never reported as PASS | PASS |
| C never reported as PASS | PASS |
| D never reported as PASS | PASS |
| Syntax error distinguished | PASS |
| Hanging submission distinguished | PASS |
| Rejected submission archived with reference | PASS |
| buggy: report and trace exist | PASS |
| buggy: mutable test databases removed | PASS |
| buggy: initial fixture restored | PASS |
| reference-patch: report and trace exist | PASS |
| reference-patch: mutable test databases removed | PASS |
| reference-patch: initial fixture restored | PASS |
| reference-workspace: report and trace exist | PASS |
| reference-workspace: mutable test databases removed | PASS |
| reference-workspace: initial fixture restored | PASS |
| buggy-repeat: report and trace exist | PASS |
| buggy-repeat: mutable test databases removed | PASS |
| buggy-repeat: initial fixture restored | PASS |
| reference-repeat: report and trace exist | PASS |
| reference-repeat: mutable test databases removed | PASS |
| reference-repeat: initial fixture restored | PASS |
| planned-B: report and trace exist | PASS |
| planned-B: mutable test databases removed | PASS |
| planned-C: report and trace exist | PASS |
| planned-C: mutable test databases removed | PASS |
| planned-D: report and trace exist | PASS |
| planned-D: mutable test databases removed | PASS |
| syntax-error: report and trace exist | PASS |
| syntax-error: mutable test databases removed | PASS |
| syntax-error: initial fixture restored | PASS |
| timeout: report and trace exist | PASS |
| timeout: mutable test databases removed | PASS |
| timeout: initial fixture restored | PASS |
| invalid-submission: report and trace exist | PASS |
| invalid-submission: mutable test databases removed | PASS |
| invalid-submission: initial fixture restored | PASS |
| Run IDs unique | PASS |
| No invented Agent or experience observations | PASS |

## 每条实际命令与原始日志

### dependency-install

开始 `2026-10-09T17:46:44.632048+00:00`，结束 `2026-10-09T17:46:45.577576+00:00`，实际退出 `0`。

```bash
<MAINTAINER_HOME>/data_storage/humble_workspace/orderflow_incident_lab/.venv/bin/python -m pip install --no-index --find-links <MAINTAINER_HOME>/data_storage/humble_workspace/orderflow_incident_lab/.wheelhouse --no-build-isolation -e .
```

[stdout](runs/validation/d961a165-2bf3-46b7-9f78-4cb2ab67e176/01-dependency-install.stdout.log) · [stderr](runs/validation/d961a165-2bf3-46b7-9f78-4cb2ab67e176/01-dependency-install.stderr.log)

### dependency-check

开始 `2026-10-09T17:46:45.577772+00:00`，结束 `2026-10-09T17:46:45.840495+00:00`，实际退出 `0`。

```bash
<MAINTAINER_HOME>/data_storage/humble_workspace/orderflow_incident_lab/.venv/bin/python -m pip check
```

[stdout](runs/validation/d961a165-2bf3-46b7-9f78-4cb2ab67e176/02-dependency-check.stdout.log) · [stderr](runs/validation/d961a165-2bf3-46b7-9f78-4cb2ab67e176/02-dependency-check.stderr.log)

### runtime

开始 `2026-10-09T17:46:45.840672+00:00`，结束 `2026-10-09T17:46:45.985561+00:00`，实际退出 `0`。

```bash
<MAINTAINER_HOME>/data_storage/humble_workspace/orderflow_incident_lab/.venv/bin/python -c 'import sys,sqlite3,pytest; print(sys.version); print('"'"'SQLite'"'"',sqlite3.sqlite_version); print('"'"'pytest'"'"',pytest.__version__)'
```

[stdout](runs/validation/d961a165-2bf3-46b7-9f78-4cb2ab67e176/03-runtime.stdout.log) · [stderr](runs/validation/d961a165-2bf3-46b7-9f78-4cb2ab67e176/03-runtime.stderr.log)

### framework-tests

开始 `2026-10-09T17:46:45.985764+00:00`，结束 `2026-10-09T17:46:56.263858+00:00`，实际退出 `0`。

```bash
<MAINTAINER_HOME>/data_storage/humble_workspace/orderflow_incident_lab/.venv/bin/python -m pytest -q --junitxml <MAINTAINER_HOME>/data_storage/humble_workspace/orderflow_incident_lab/runs/validation/d961a165-2bf3-46b7-9f78-4cb2ab67e176/framework.junit.xml
```

[stdout](runs/validation/d961a165-2bf3-46b7-9f78-4cb2ab67e176/04-framework-tests.stdout.log) · [stderr](runs/validation/d961a165-2bf3-46b7-9f78-4cb2ab67e176/04-framework-tests.stderr.log)

### episode-list

开始 `2026-10-09T17:46:56.264039+00:00`，结束 `2026-10-09T17:46:56.373616+00:00`，实际退出 `0`。

```bash
<MAINTAINER_HOME>/data_storage/humble_workspace/orderflow_incident_lab/.venv/bin/orderflow list
```

[stdout](runs/validation/d961a165-2bf3-46b7-9f78-4cb2ab67e176/05-episode-list.stdout.log) · [stderr](runs/validation/d961a165-2bf3-46b7-9f78-4cb2ab67e176/05-episode-list.stderr.log)

### validate-smoke

开始 `2026-10-09T17:46:56.373989+00:00`，结束 `2026-10-09T17:46:56.477258+00:00`，实际退出 `0`。

```bash
<MAINTAINER_HOME>/data_storage/humble_workspace/orderflow_incident_lab/.venv/bin/orderflow validate --episode SMOKE-001
```

[stdout](runs/validation/d961a165-2bf3-46b7-9f78-4cb2ab67e176/06-validate-smoke.stdout.log) · [stderr](runs/validation/d961a165-2bf3-46b7-9f78-4cb2ab67e176/06-validate-smoke.stderr.log)

### business-path

开始 `2026-10-09T17:46:56.477651+00:00`，结束 `2026-10-09T17:46:56.519557+00:00`，实际退出 `0`。

```bash
<MAINTAINER_HOME>/data_storage/humble_workspace/orderflow_incident_lab/.venv/bin/python -c 'import json,tempfile
from pathlib import Path
from app.service import OrderFlow
with tempfile.TemporaryDirectory() as d:
 f=OrderFlow(Path(d)/"business.sqlite"); f.initialize({"SKU-1":10})
 values=[f.get_inventory("SKU-1")["available"]]
 f.create_order("demo","SKU-1",3); values.append(f.get_inventory("SKU-1")["available"])
 f.cancel_order("demo"); values.append(f.get_inventory("SKU-1")["available"])
 f.cancel_order("demo"); values.append(f.get_inventory("SKU-1")["available"])
 print(json.dumps({"available":values,"audit":f.audit()["consistent"]}))
'
```

[stdout](runs/validation/d961a165-2bf3-46b7-9f78-4cb2ab67e176/07-business-path.stdout.log) · [stderr](runs/validation/d961a165-2bf3-46b7-9f78-4cb2ab67e176/07-business-path.stderr.log)

### prepare-smoke

开始 `2026-10-09T17:46:56.519908+00:00`，结束 `2026-10-09T17:46:56.648798+00:00`，实际退出 `0`。

```bash
<MAINTAINER_HOME>/data_storage/humble_workspace/orderflow_incident_lab/.venv/bin/orderflow prepare --episode SMOKE-001
```

[stdout](runs/validation/d961a165-2bf3-46b7-9f78-4cb2ab67e176/08-prepare-smoke.stdout.log) · [stderr](runs/validation/d961a165-2bf3-46b7-9f78-4cb2ab67e176/08-prepare-smoke.stderr.log)

### file-isolation

开始 `2026-10-09T17:46:56.649068+00:00`，结束 `2026-10-09T17:46:56.787162+00:00`，实际退出 `0`。

```bash
<MAINTAINER_HOME>/data_storage/humble_workspace/orderflow_incident_lab/.venv/bin/orderflow shell --run-id 1b748db5-2da1-4f12-bc0c-5309ac794027 -- /usr/bin/python3.12 -c 'from pathlib import Path; import json; blocked=[not Path(p).exists() for p in ['"'"'<MAINTAINER_HOME>/data_storage/humble_workspace/orderflow_incident_lab/evaluator'"'"', '"'"'<MAINTAINER_HOME>/data_storage/humble_workspace/orderflow_incident_lab/app'"'"', '"'"'<MAINTAINER_HOME>/data_storage/humble_workspace/orderflow_incident_lab/docs'"'"', '"'"'/proc/1/root<MAINTAINER_HOME>/data_storage/humble_workspace/orderflow_incident_lab/evaluator'"'"']]; print(json.dumps({'"'"'blocked'"'"':blocked})); assert all(blocked)'
```

[stdout](runs/validation/d961a165-2bf3-46b7-9f78-4cb2ab67e176/09-file-isolation.stdout.log) · [stderr](runs/validation/d961a165-2bf3-46b7-9f78-4cb2ab67e176/09-file-isolation.stderr.log)

### public-smoke

开始 `2026-10-09T17:46:56.787536+00:00`，结束 `2026-10-09T17:46:56.958751+00:00`，实际退出 `0`。

```bash
<MAINTAINER_HOME>/data_storage/humble_workspace/orderflow_incident_lab/.venv/bin/orderflow shell --run-id 1b748db5-2da1-4f12-bc0c-5309ac794027 -- /usr/bin/python3.12 -m unittest discover -s tests/public
```

[stdout](runs/validation/d961a165-2bf3-46b7-9f78-4cb2ab67e176/10-public-smoke.stdout.log) · [stderr](runs/validation/d961a165-2bf3-46b7-9f78-4cb2ab67e176/10-public-smoke.stderr.log)

### actual-defect-path

开始 `2026-10-09T17:46:56.959081+00:00`，结束 `2026-10-09T17:46:57.102769+00:00`，实际退出 `0`。

```bash
<MAINTAINER_HOME>/data_storage/humble_workspace/orderflow_incident_lab/.venv/bin/orderflow shell --run-id 1b748db5-2da1-4f12-bc0c-5309ac794027 -- /usr/bin/python3.12 -c 'from app.service import OrderFlow
import json
f=OrderFlow('"'"'/tmp/defect.sqlite'"'"'); f.initialize({'"'"'SKU-1'"'"':10})
v=[f.get_inventory('"'"'SKU-1'"'"')['"'"'available'"'"']]
f.create_order('"'"'defect'"'"','"'"'SKU-1'"'"',3);v.append(f.get_inventory('"'"'SKU-1'"'"')['"'"'available'"'"'])
f.cancel_order('"'"'defect'"'"');v.append(f.get_inventory('"'"'SKU-1'"'"')['"'"'available'"'"'])
f.cancel_order('"'"'defect'"'"');v.append(f.get_inventory('"'"'SKU-1'"'"')['"'"'available'"'"'])
print(json.dumps({'"'"'available'"'"':v})); assert v==[10,7,10,13]
'
```

[stdout](runs/validation/d961a165-2bf3-46b7-9f78-4cb2ab67e176/11-actual-defect-path.stdout.log) · [stderr](runs/validation/d961a165-2bf3-46b7-9f78-4cb2ab67e176/11-actual-defect-path.stderr.log)

### buggy-evaluation

开始 `2026-10-09T17:46:57.103130+00:00`，结束 `2026-10-09T17:46:58.321819+00:00`，实际退出 `1`。

```bash
<MAINTAINER_HOME>/data_storage/humble_workspace/orderflow_incident_lab/.venv/bin/orderflow evaluate --episode SMOKE-001 --run-id 1b748db5-2da1-4f12-bc0c-5309ac794027
```

[stdout](runs/validation/d961a165-2bf3-46b7-9f78-4cb2ab67e176/12-buggy-evaluation.stdout.log) · [stderr](runs/validation/d961a165-2bf3-46b7-9f78-4cb2ab67e176/12-buggy-evaluation.stderr.log)

### reference-patch

开始 `2026-10-09T17:46:58.322725+00:00`，结束 `2026-10-09T17:46:59.971402+00:00`，实际退出 `0`。

```bash
<MAINTAINER_HOME>/data_storage/humble_workspace/orderflow_incident_lab/.venv/bin/orderflow evaluate --episode SMOKE-001 --submission <MAINTAINER_HOME>/data_storage/humble_workspace/orderflow_incident_lab/evaluator/reference_patches/SMOKE-001.diff
```

[stdout](runs/validation/d961a165-2bf3-46b7-9f78-4cb2ab67e176/13-reference-patch.stdout.log) · [stderr](runs/validation/d961a165-2bf3-46b7-9f78-4cb2ab67e176/13-reference-patch.stderr.log)

### reference-workspace

开始 `2026-10-09T17:46:59.972355+00:00`，结束 `2026-10-09T17:47:01.617716+00:00`，实际退出 `0`。

```bash
<MAINTAINER_HOME>/data_storage/humble_workspace/orderflow_incident_lab/.venv/bin/orderflow evaluate --episode SMOKE-001 --submission <MAINTAINER_HOME>/data_storage/humble_workspace/orderflow_incident_lab/app
```

[stdout](runs/validation/d961a165-2bf3-46b7-9f78-4cb2ab67e176/14-reference-workspace.stdout.log) · [stderr](runs/validation/d961a165-2bf3-46b7-9f78-4cb2ab67e176/14-reference-workspace.stderr.log)

### report-query

开始 `2026-10-09T17:47:01.618675+00:00`，结束 `2026-10-09T17:47:01.724617+00:00`，实际退出 `0`。

```bash
<MAINTAINER_HOME>/data_storage/humble_workspace/orderflow_incident_lab/.venv/bin/orderflow report --run-id a8e532fa-a638-4c58-88f4-fb8896f14213
```

[stdout](runs/validation/d961a165-2bf3-46b7-9f78-4cb2ab67e176/15-report-query.stdout.log) · [stderr](runs/validation/d961a165-2bf3-46b7-9f78-4cb2ab67e176/15-report-query.stderr.log)

### reset-smoke

开始 `2026-10-09T17:47:01.725629+00:00`，结束 `2026-10-09T17:47:01.939516+00:00`，实际退出 `0`。

```bash
<MAINTAINER_HOME>/data_storage/humble_workspace/orderflow_incident_lab/.venv/bin/orderflow reset --episode SMOKE-001
```

[stdout](runs/validation/d961a165-2bf3-46b7-9f78-4cb2ab67e176/16-reset-smoke.stdout.log) · [stderr](runs/validation/d961a165-2bf3-46b7-9f78-4cb2ab67e176/16-reset-smoke.stderr.log)

### buggy-repeat

开始 `2026-10-09T17:47:01.939869+00:00`，结束 `2026-10-09T17:47:03.176200+00:00`，实际退出 `1`。

```bash
<MAINTAINER_HOME>/data_storage/humble_workspace/orderflow_incident_lab/.venv/bin/orderflow evaluate --episode SMOKE-001
```

[stdout](runs/validation/d961a165-2bf3-46b7-9f78-4cb2ab67e176/17-buggy-repeat.stdout.log) · [stderr](runs/validation/d961a165-2bf3-46b7-9f78-4cb2ab67e176/17-buggy-repeat.stderr.log)

### reference-repeat

开始 `2026-10-09T17:47:03.177012+00:00`，结束 `2026-10-09T17:47:04.823029+00:00`，实际退出 `0`。

```bash
<MAINTAINER_HOME>/data_storage/humble_workspace/orderflow_incident_lab/.venv/bin/orderflow evaluate --episode SMOKE-001 --submission <MAINTAINER_HOME>/data_storage/humble_workspace/orderflow_incident_lab/evaluator/reference_patches/SMOKE-001.diff
```

[stdout](runs/validation/d961a165-2bf3-46b7-9f78-4cb2ab67e176/18-reference-repeat.stdout.log) · [stderr](runs/validation/d961a165-2bf3-46b7-9f78-4cb2ab67e176/18-reference-repeat.stderr.log)

### validate-implemented-A

开始 `2026-10-09T17:47:04.824025+00:00`，结束 `2026-10-09T17:47:04.927732+00:00`，实际退出 `0`。

```bash
<MAINTAINER_HOME>/data_storage/humble_workspace/orderflow_incident_lab/.venv/bin/orderflow validate --episode A
```

[stdout](runs/validation/d961a165-2bf3-46b7-9f78-4cb2ab67e176/19-validate-implemented-A.stdout.log) · [stderr](runs/validation/d961a165-2bf3-46b7-9f78-4cb2ab67e176/19-validate-implemented-A.stderr.log)

### validate-planned-B

开始 `2026-10-09T17:47:04.927923+00:00`，结束 `2026-10-09T17:47:05.030767+00:00`，实际退出 `4`。

```bash
<MAINTAINER_HOME>/data_storage/humble_workspace/orderflow_incident_lab/.venv/bin/orderflow validate --episode B
```

[stdout](runs/validation/d961a165-2bf3-46b7-9f78-4cb2ab67e176/20-validate-planned-B.stdout.log) · [stderr](runs/validation/d961a165-2bf3-46b7-9f78-4cb2ab67e176/20-validate-planned-B.stderr.log)

### evaluate-planned-B

开始 `2026-10-09T17:47:05.030949+00:00`，结束 `2026-10-09T17:47:05.133536+00:00`，实际退出 `4`。

```bash
<MAINTAINER_HOME>/data_storage/humble_workspace/orderflow_incident_lab/.venv/bin/orderflow evaluate --episode B
```

[stdout](runs/validation/d961a165-2bf3-46b7-9f78-4cb2ab67e176/21-evaluate-planned-B.stdout.log) · [stderr](runs/validation/d961a165-2bf3-46b7-9f78-4cb2ab67e176/21-evaluate-planned-B.stderr.log)

### validate-planned-C

开始 `2026-10-09T17:47:05.133940+00:00`，结束 `2026-10-09T17:47:05.235199+00:00`，实际退出 `4`。

```bash
<MAINTAINER_HOME>/data_storage/humble_workspace/orderflow_incident_lab/.venv/bin/orderflow validate --episode C
```

[stdout](runs/validation/d961a165-2bf3-46b7-9f78-4cb2ab67e176/22-validate-planned-C.stdout.log) · [stderr](runs/validation/d961a165-2bf3-46b7-9f78-4cb2ab67e176/22-validate-planned-C.stderr.log)

### evaluate-planned-C

开始 `2026-10-09T17:47:05.235603+00:00`，结束 `2026-10-09T17:47:05.339814+00:00`，实际退出 `4`。

```bash
<MAINTAINER_HOME>/data_storage/humble_workspace/orderflow_incident_lab/.venv/bin/orderflow evaluate --episode C
```

[stdout](runs/validation/d961a165-2bf3-46b7-9f78-4cb2ab67e176/23-evaluate-planned-C.stdout.log) · [stderr](runs/validation/d961a165-2bf3-46b7-9f78-4cb2ab67e176/23-evaluate-planned-C.stderr.log)

### validate-planned-D

开始 `2026-10-09T17:47:05.340020+00:00`，结束 `2026-10-09T17:47:05.446721+00:00`，实际退出 `4`。

```bash
<MAINTAINER_HOME>/data_storage/humble_workspace/orderflow_incident_lab/.venv/bin/orderflow validate --episode D
```

[stdout](runs/validation/d961a165-2bf3-46b7-9f78-4cb2ab67e176/24-validate-planned-D.stdout.log) · [stderr](runs/validation/d961a165-2bf3-46b7-9f78-4cb2ab67e176/24-validate-planned-D.stderr.log)

### evaluate-planned-D

开始 `2026-10-09T17:47:05.447035+00:00`，结束 `2026-10-09T17:47:05.550147+00:00`，实际退出 `4`。

```bash
<MAINTAINER_HOME>/data_storage/humble_workspace/orderflow_incident_lab/.venv/bin/orderflow evaluate --episode D
```

[stdout](runs/validation/d961a165-2bf3-46b7-9f78-4cb2ab67e176/25-evaluate-planned-D.stdout.log) · [stderr](runs/validation/d961a165-2bf3-46b7-9f78-4cb2ab67e176/25-evaluate-planned-D.stderr.log)

### syntax-error

开始 `2026-10-09T17:47:05.551715+00:00`，结束 `2026-10-09T17:47:06.386330+00:00`，实际退出 `2`。

```bash
<MAINTAINER_HOME>/data_storage/humble_workspace/orderflow_incident_lab/.venv/bin/orderflow evaluate --episode SMOKE-001 --submission <MAINTAINER_HOME>/data_storage/humble_workspace/orderflow_incident_lab/runs/validation/d961a165-2bf3-46b7-9f78-4cb2ab67e176/syntax-submission
```

[stdout](runs/validation/d961a165-2bf3-46b7-9f78-4cb2ab67e176/26-syntax-error.stdout.log) · [stderr](runs/validation/d961a165-2bf3-46b7-9f78-4cb2ab67e176/26-syntax-error.stderr.log)

### timeout

开始 `2026-10-09T17:47:06.387930+00:00`，结束 `2026-10-09T17:47:07.553284+00:00`，实际退出 `3`。

```bash
<MAINTAINER_HOME>/data_storage/humble_workspace/orderflow_incident_lab/.venv/bin/orderflow evaluate --episode SMOKE-001 --submission <MAINTAINER_HOME>/data_storage/humble_workspace/orderflow_incident_lab/runs/validation/d961a165-2bf3-46b7-9f78-4cb2ab67e176/timeout-submission --timeout 1
```

[stdout](runs/validation/d961a165-2bf3-46b7-9f78-4cb2ab67e176/27-timeout.stdout.log) · [stderr](runs/validation/d961a165-2bf3-46b7-9f78-4cb2ab67e176/27-timeout.stderr.log)

### invalid-submission

开始 `2026-10-09T17:47:07.553785+00:00`，结束 `2026-10-09T17:47:07.694274+00:00`，实际退出 `2`。

```bash
<MAINTAINER_HOME>/data_storage/humble_workspace/orderflow_incident_lab/.venv/bin/orderflow evaluate --episode SMOKE-001 --submission <MAINTAINER_HOME>/data_storage/humble_workspace/orderflow_incident_lab/runs/validation/d961a165-2bf3-46b7-9f78-4cb2ab67e176/missing.diff
```

[stdout](runs/validation/d961a165-2bf3-46b7-9f78-4cb2ab67e176/28-invalid-submission.stdout.log) · [stderr](runs/validation/d961a165-2bf3-46b7-9f78-4cb2ab67e176/28-invalid-submission.stderr.log)

## 限制与停止边界

文件隔离、独立判分、数据库重置和手动提交流水线已验收；Phase 2 增加宿主数据库 Oracle。网络未隔离；CPU/内存/seccomp、敌对 RPC 限流、完整反作弊、原生 Windows、wheel 发布和同 Run 并发未验证或未实现。
Payment/Event 是契约；Codex 自动接入未实现；经验四接口为 Disabled。无 Agent 运行指标、经验命中/决策/反馈或正式对照结果。
本结论覆盖 Phase 1 回归。原始 Phase 1 验收记录保留在其 validation Run；Phase 2 结论见独立报告。
