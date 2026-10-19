# CLI 与运行环境

普通 Linux/WSL2 环境用 Python 3.12 建立 venv 并 `pip install -e .`，随后使用 `.venv/bin/orderflow`。安装固定依赖需要网络，或提供匹配的离线 wheelhouse；`bubblewrap` 与 `git` 属于系统依赖。

## 本机实际验证环境

系统 Python 是 3.10，本机 Flatpak Runtime 提供 Python 3.12.13。当前环境下载域名解析失败，因此使用 `scripts/python312` 在已安装 Runtime 中运行；此脚本不影响系统 Python，也不安装系统软件。

`.runtime.env` 保存本机 Runtime 的 `files` 目录：

```bash
ORDERFLOW_PYTHON_RUNTIME='<MAINTAINER_HOME>/.local/share/flatpak/runtime/org.freedesktop.Platform/x86_64/24.08/9a6d66049b19987a22bf81015ce0d1fde260df85a45e54695aad3c82f1e198ee/files'
```

本地离线安装流程（需本机已有固定版本的纯 Python 依赖）：

```bash
python3 scripts/rebuild_local_wheels.py
scripts/python312 -m venv .venv
scripts/python312 -m pip install --no-index --find-links .wheelhouse setuptools==76.1.0 wheel==0.45.1
scripts/python312 -m pip install --no-index --find-links .wheelhouse --no-build-isolation -e .
scripts/python312 -m pip check
```

这些 wheel 为从本机已安装纯 Python 包重建的快照，保留许可证和 metadata，不宣称来自重新下载的供应商 wheel。`.venv/`、`.wheelhouse/`、`.runtime.env` 不属于源码交付；在其他机器应使用常规 Python 3.12 安装，或配置自己的 Runtime 路径。脚本假定本机目录存在，未实现 Runtime 下载/自动发现。

## 命令

以下使用本机入口 `scripts/orderflow`，它调用已安装的同一 `orderflow` entry point。

| 命令 | 行为 |
|---|---|
| `scripts/orderflow list` | 列出实现状态和版本 |
| `scripts/orderflow validate --episode SMOKE-001` | 校验 public/private manifest，返回 READY |
| `scripts/orderflow validate --episode A --variant v01` | 校验 Episode A 与变体，返回 READY |
| `scripts/orderflow validate --episode B` | manifest 有效，但 NOT_IMPLEMENTED，退出 4；C 相同 |
| `scripts/orderflow prepare --episode SMOKE-001` | 新建唯一 Run、缺陷代码副本与初始数据库 |
| `scripts/orderflow prepare --episode A --variant v01` | 建立 stale-snapshot 缺陷工作区和初始 50 件库存 |
| `scripts/orderflow shell --run-id <id> -- <command>` | 在实际文件隔离中执行公开工作区命令 |
| `scripts/orderflow evaluate --episode SMOKE-001 --run-id <id>` | 评测该准备工作区快照 |
| `scripts/orderflow evaluate --episode SMOKE-001 --submission <path>` | 新建 Run，接收 patch 或 app 工作区 |
| `scripts/orderflow evaluate --episode SMOKE-001 --submission <path> --timeout 1` | 将默认 20 秒限额缩短至 1 秒 |
| `scripts/orderflow evaluate --episode A --variant v01 --submission evaluator/reference_patches/A-v01.diff` | 新建 A Run、应用维护者参考补丁、执行 A 的 14 项私有测试 |
| `scripts/orderflow evaluate --episode A --submission <workspace>` | 复制候选 app 源码，独立评测；忽略候选测试配置 |
| `scripts/orderflow report --run-id <id>` | 查询已归档 JSON，不重新测试 |
| `scripts/orderflow reset --episode SMOKE-001` | 恢复该 Episode 的业务数据库，保留代码和报告 |
| `scripts/orderflow reset --episode A` | 仅重置 A 的运行数据，保留其代码与归档 |

全局 `--runs-root <path>` 置于子命令前，指定宿主归档根。例如 `scripts/orderflow --runs-root runs/local prepare --episode SMOKE-001`。后续查询和重置需使用同一根目录。

Evaluate 省略 submission 和 run-id 时，自动准备并评测该 Episode 的默认缺陷版本。已结束 Run 不再用于评测；新建 Run 重复执行。Reset 恢复数据，不撤销代码修改，也不把旧 FAIL 改成 PASS。B/C 的准备、评测和重置返回 NOT_IMPLEMENTED，不执行故障场景。

当前变体为 `SMOKE-001/default`、`A/v01` 与 `D/v01`。A 的 fixture 将 v01 映射为 `stale-snapshot`。`--variant` 支持 validate、prepare、evaluate；未知变体或与已准备 Run 不一致的变体返回 ERROR。A/D 默认评测上限 120 秒，Smoke 20 秒；`--timeout` 只能降低对应私有配置的上限。`--episode` 和 `--run-id` 不匹配时返回 ERROR。

## Episode A 复现与回归

以下命令由维护者在宿主执行；私有补丁与输出归档不交给被测 Agent。

```bash
# 单独复现基准竞争；工具输出包含并发 RPC 与独立数据库证据
scripts/python312 scripts/reproduce_episode_a.py
scripts/python312 scripts/reproduce_episode_a.py \
  --submission evaluator/reference_patches/A-v01.diff

# 完整私有 suite；分别预期退出 1 / 0
scripts/orderflow evaluate --episode A --variant v01
scripts/orderflow evaluate --episode A --variant v01 \
  --submission evaluator/reference_patches/A-v01.diff

# 原有开发者测试和 Phase 1 生命周期回归
scripts/python312 -m pytest -q
scripts/python312 scripts/validate_phase1.py

# Phase 2 一键验收：含 Phase 1 回归与 10 轮独立 Buggy/Reference 对照
scripts/python312 scripts/validate_phase2.py
```

复现器用于观察一个基准 batch，正式判分应使用 `orderflow evaluate`。连续独立初始化的 10 轮 Buggy/Reference 对照、命令真实退出状态和最终验收结论见 [Phase 2 验收报告](../PHASE2_VALIDATION_REPORT.md)。

Run 的可信 Evaluator/Fixture/Suite/私有配置和环境指纹在准备时记录，在评测前后重算；期间变化将判 ERROR 并要求重新创建 Run。修改 Agent 公开工作区中的 app 是正常提交动作，不会改变宿主可信评测源码指纹。

CLI stdout 为 JSON；shell 转发子进程真实输出。命令错误通过 stderr 返回 JSON。

| 退出状态 | 意义 |
|---|---|
| 0 | PASS、准备/重置成功、列表、成功读取报告 |
| 1 | FAIL，真实断言失败 |
| 2 | ERROR，提交、启动、评测、结果完整性或重置错误 |
| 3 | TIMEOUT |
| 4 | NOT_IMPLEMENTED |
| 5 | CANCELLED，已明确取消或 Collector 中断；不等于业务 FAIL |

`report/status/snapshot` 成功读取终态报告时退出 0：这是查询成功，不是任务通过。

## Phase 3 历史原生执行入口

```bash
scripts/orderflow run-codex --episode A --variant v01 --agent-timeout 900
ORDERFLOW_ENABLE_CODEX=1 scripts/python312 scripts/validate_phase3.py
```

`run-codex` 每次生成新 Run 和新原生会话，先构建公开 Participant，再提取实际 app diff，使用相同 Episode 的独立 Evaluator。`--evaluation-timeout` 只允许降低既有评测上限；`--agent-timeout` 为 (0,7200] 秒。`--model` 默认当前验证的 `gpt-6.1-sol`。未实现的 B/C 返回 NOT_IMPLEMENTED，不启动 Agent。

以上是 Phase 3 的历史配置；当前新 Live 使用下文 Gateway 与 M1.1 策略，不继承早期 OAuth/model 配置。旧验收脚本可能写入历史，必须另建归档而不能直接覆盖。

常规 Python 3.12 环境使用 `.venv/bin/orderflow run-codex`，并由可信启动器设置 `ORDERFLOW_CODEX_BINARY` 和 `ORDERFLOW_CODEX_AUTH_PATH`。这些是宿主参数，不会传入 Participant 环境。当前机器 `scripts/orderflow` 自动为该子命令启用原生启动配置；身份文件仅挂入可信维护者 namespace，Participant 不挂载该目录。详见 [Codex 配置](CODEX_INTEGRATION.md)。

完整 Phase 3 验收及归档复核：

```bash
ORDERFLOW_ENABLE_CODEX=1 scripts/python312 scripts/validate_phase3.py --agent-timeout 900
ORDERFLOW_ENABLE_CODEX=1 scripts/python312 scripts/audit_phase3_evidence.py --validation-id <validation_uuid>
```

归档复核重跑开发者测试，重解析原始 JSONL，并核对版本与隔离证据；不会再次调用模型或改变 Agent 原始成绩。

## Phase 3.5 hardened live entry

Use the safe host secret setup in [GATEWAY_PROVIDER.md](GATEWAY_PROVIDER.md), then:

```bash
ORDERFLOW_ENABLE_CODEX=1 scripts/orderflow --runs-root phase3_5_validation/new-validation/runs run-codex --episode A --provider gateway --model gpt-5.6-terra --reasoning-effort max --agent-timeout 900 --request-budget 160
```

The secret value is never a CLI argument. Missing kernel delegation, official helper or model credentials fails closed. New live Legacy entry is blocked; historical/manual evaluation remains supported. The report distinguishes runtime, native collaboration, submission integrity, evaluation, isolation and integration.

## M1 Episode D

D 的 `validate/prepare/evaluate/report/reset/run-codex` 复用原 CLI。`D/v01` 是多独立 Worker 共享 SQLite 场景。Private Suite 当前28项，通过条件仍是完整必要集合、真实退出码、无skip/error及独立数据库不变量；不能单看计数。

```sh
scripts/orderflow validate --episode D --variant v01
scripts/orderflow --runs-root m1_validation/local-runs prepare --episode D
scripts/orderflow --runs-root m1_validation/local-runs evaluate --episode D
scripts/orderflow --runs-root m1_validation/local-runs evaluate --episode D \
  --submission evaluator/reference_patches/D-v01.diff
scripts/orderflow --runs-root m1_validation/local-runs report --run-id <uuid>
scripts/orderflow --runs-root m1_validation/local-runs reset --episode D
scripts/python312 scripts/reproduce_episode_d.py --archive m1_validation/new-repeat --rounds 10
ORDERFLOW_ENABLE_CODEX=1 scripts/orderflow --runs-root m1_validation/new-live/runs \
  run-codex --episode D --provider gateway --model gpt-5.6-terra \
  --reasoning-effort max --agent-timeout 1200 --request-budget 160
```

这些是命令模板；实际命令及结果归档于M1报告。历史Phase1/2/3脚本可能覆盖旧报告；不得为当前回归直接运行覆盖入口。Phase3.5的 `phase35_offline.py` 保留当时D=PLANNED合同，M1先在原基线上执行它，再使用新的当前态回归。维护者分析与私有标签见 [EPISODE_D.md](EPISODE_D.md)，不复制给Participant。

## M1.1 execution and live control

`bounded` remains the default: total timeout 900 seconds, request budget 160, native multi-agent enabled. Completion-aware must be selected explicitly together with `--agent-timeout none`; it sets both watchdog wall limits and collector total deadline to `None`. `--request-budget none` is accepted only in this mode. Finite CPU/memory/process/output/concurrency limits remain. `--stream-idle-timeout-ms` is the installed official CLI's network idle setting; `--connect-timeout-seconds` bounds socket/TLS connection establishment separately from the subsequent response.

```sh
ORDERFLOW_ENABLE_CODEX=1 scripts/orderflow --runs-root m1_1_validation/new-live/runs \
  run-codex --episode D --provider gateway --model gpt-5.6-terra \
  --reasoning-effort max --completion-policy completion-aware \
  --agent-timeout none --request-budget none --agent-mode multi
scripts/orderflow --runs-root m1_1_validation/new-live/runs status --run-id <uuid>
scripts/orderflow --runs-root m1_1_validation/new-live/runs snapshot --run-id <uuid>
scripts/orderflow --runs-root m1_1_validation/new-live/runs cancel --run-id <uuid> --reason 'operator decision'
```

These are trusted-host commands. A live snapshot is `PARTIAL_SNAPSHOT`; first observed source change does not establish hidden-test readiness. Cancel uses the bound Run/control identity rather than sending a signal to a caller-namespace PID. Already-terminal, missing or mismatched Runs reject cancellation. `single` disables official `multi_agent` and `agents.enabled`, removes public role files, and must also be verified from actual logs. No automatic resume is claimed.

## M1.1 Audit-Lite commands

```sh
# Output parent must exist and be outside Full Archive; existing ZIPs are refused.
scripts/orderflow export --full-archive <sealed-full-archive> --output <new-audit.zip> \
  --created-at 2026-10-10T00:00:00Z
scripts/orderflow inspect <new-audit.zip>
scripts/orderflow verify <new-audit.zip>
# Trusted standalone stdlib verifier, usable with -I from an empty working directory.
python3 -I /path/to/trusted/benchmark/evidence_verify.py verify <new-audit.zip> --json
```

Fixed `created-at` makes identical input byte output deterministic with the same compressor. Verification succeeds with exit 0, refuses unsafe/inconsistent packages with exit 2, and neither extracts ZIP contents nor executes their code. The bundled verifier is a convenience copy; reviewers should obtain the trusted verifier independently. Included exported bytes and their internal relationships are checked; hashes of `NOT_INCLUDED` originals are pointers, not verification of those absent bytes. The bundle is **MAINTAINER_AUDIT**, never a Participant input. Details: [EVIDENCE_EXPORT_POLICY.md](EVIDENCE_EXPORT_POLICY.md).
