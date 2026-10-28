# 普通项目：从候选到下一次复用

本页接续[快速开始](QUICKSTART.md)中的 MCP 提议。普通项目使用公开 Core 的
`source-project`，不需要 OrderFlow、私有 Evaluator 或手工写图节点。
候选自测、独立来源核验、有界审批和发布分别完成；Console 只读。

这里的有界审批可以由项目负责人预先授权的自动化作业执行，不要求人逐条查看所有
记忆。普通观察和草稿可以自动保存并作为低信任线索检索；只有晋升为受支持经验时，
才需要配置允许的独立证据。固定的验证器和晋升范围由可信管理通道设置，候选 Agent
不能自行扩大。人工处理范围外内容、冲突和策略调整；不把人工点击当成证据。

普通 Agent 可用 `search_observations`或`aevora observations '具体关键词'`找到历史
草稿作为线索。它们仍是原始声明，不进入已发布经验的适用性结果，也不能用候选 ID
冒充 Experience 记录 APPLY。核验器须由 Host 授权并固定 suite/runner，执行实际提交，
从独立作业输出接收授权 receipt pin；提议者提交的自测或 checksum 不建立信任。
运行时版本与源码版本可用于将规则限定到实际测量的固定实现，不从单次 PASS 外推到
其他构建或所有重启/故障场景。后续真实任务应保留查询、证据读取、选择声明与实际结果，
分别表达已观察到的结果、是否采纳和因果收益。

尚未确定必要条件或适用范围的观察，也可通过 `propose_experience`保存为未核验
草稿：相应对象使用 `{}`，将不确定性写入 limitations，不填造事实或无关条件。
返回的 `scope_status=UNSCOPED_DRAFT`与 next_step 说明后续操作。草稿保留为
PROPOSED，不会被查询当作可用经验，也不能通过准入或发布。条件明确后，使用
新的 candidate_key 提交有界候选，保留原草稿；候选内容不可原地改写。

这使普通工程观察能够先被记录；当前自动适用性判断仍使用明确的公共事实词汇。
领域词汇不足时不把自然语言说明伪装成机器已经核验的适用条件。

原生用户可先用可读计划整理候选，不必先理解完整生命周期命令：

```sh
aevora --project NAME candidate plan CANDIDATE_ID
aevora --project NAME context collect --json
aevora --project NAME candidate derive --from CANDIDATE_ID --key NEW_KEY \
  --conditions '{"runtime_engine":["go_native"]}' \
  --scope '{"storage_backend":["sqlite"]}'
aevora --project NAME candidate plan NEW_CANDIDATE_ID
```

示例仅展示格式，条件须来自自己的实际任务；不能为通过门槛照填。`derive`保留原
候选、原 Run 和引用，生成新 body 摘要与 `derived_from_candidate_id`，没有授予核验或
发布权限。原有 unknown_fields 和限制继续保留，未建立的关键事实仍会阻断准入。
计划显示缺少的字段、未确定的关键事实、已有来源能否支持声明范围，以及当前 head；
它复用实际准入校验，不把声明范围当作证据。完成来源导入后再次读取计划与当前 head。

Console 的“核验与发布”展示标题、摘要、声明条件、缺项和下一步；打开生命周期证据
可查看独立来源检查及原始公开记录。Web 始终只读；来源导入和审批使用可信 CLI。

原生Go与Python对照使用相同的project policy/receipt契约。原生Host可保持运行，
管理命令通过独立可信通道调用；消费者MCP没有source/review权限。

```sh
aevora inspect CANDIDATE_ID
aevora source-project --candidate CANDIDATE_ID --policy /absolute/host/policy.json --evidence-root /absolute/artifacts --receipt-sha256 APPROVED_PIN
aevora review --candidate CANDIDATE_ID --state EVIDENCE_PENDING --expected-head HEAD_SHA --event-key pending --reason 'Independent verification required'
aevora review --candidate CANDIDATE_ID --state ADMITTED_BOUNDED --expected-head NEW_HEAD_SHA --event-key admit --reason 'Independently verified bounded scope' --source SOURCE_ID --scope '{"shared_state_kind":["sqlite_file"]}'
aevora review --candidate CANDIDATE_ID --state PUBLISHED --expected-head ADMITTED_HEAD_SHA --event-key publish --reason 'Publish reviewed scope'
aevora feedback SOURCE_ID
```

示例ID、摘要和scope必须来自自己的记录与独立事实；每次review先inspect当前head。
原生命令输出`result`和`operation_id`，相同Run事实保持固定，下一任务使用新Run。
`context catalog`说明当前可用的领域词汇和支持上下文。运行时条件不证明任意工程
结论；来源策略只写独立验证器实际建立的事实，不把自动采集值当成测试结果。
以下Python walkthrough保留为开发/对照示例，不是原生用户运行依赖。

## 由可信作业自动核验和晋升

原生 Go/SQLite 提供 `candidate automate`，供受保护的 CI 或本地验证作业在收到
独立 receipt 后调用。项目负责人预先设置策略，不必逐条执行 pending、admit、publish。
命令不会启动模型、执行产物中的脚本或自行产生可信 receipt；后台作业触发由现有
CI/本地作业系统负责。未建立范围的草稿仍可自动保存和检索为观察。

自动化策略位于所属用户私有目录（0700），文件为 0600，与候选可写目录分开：

```sh
aevora --project NAME candidate automation-policy --name local-project-ci \
  --source-policy /absolute/protected/verifier-policy.json \
  --scope '{"concurrency_scope":["independent_processes"]}' \
  --target-state PUBLISHED --output /absolute/protected/automation.json
```

此命令自动绑定所选项目和验证器策略摘要，只创建新的策略文件，不处理候选，已有文件
拒绝覆盖。以下 JSON 说明生成结构，普通用户不需要手工计算 canonical 摘要：

```json
{
  "schema_version": "aevora.automation-policy/1",
  "policy_id": "local-project-ci",
  "backend_id": "SELECTED_PROJECT_BACKEND_SHA256",
  "source_policy_sha256": "CANONICAL_VERIFIER_POLICY_SHA256",
  "scope": {"concurrency_scope": ["independent_processes"]},
  "target_state": "PUBLISHED"
}
```

两个 SHA256 示例值必须替换为所选项目的 backend 身份和 verifier policy 的 canonical
JSON 摘要，不是任意 JSON 文件的字节摘要。策略绑定该数据库和验证器；`scope`须来自
此项目实际允许的条件，示例并发条件不适用于所有工程。`target_state`也可为
`ADMITTED_BOUNDED`，随后另一个获准作业在相同来源和范围内完成发布。

```sh
aevora --project NAME candidate automate \
  --candidate CANDIDATE_ID --expected-head INSPECTED_HEAD_SHA256 \
  --policy /absolute/protected/automation.json \
  --source-policy /absolute/protected/verifier-policy.json \
  --evidence-root /absolute/independent-job/artifacts \
  --receipt-sha256 AUTHORIZED_RECEIPT_PIN
```

head 和 receipt pin 由可信作业取得，不采用提议者自报的核验结果。命令复用原有
固定 suite/runner、JUnit 和来源检查，再根据策略收窄声明范围，执行既有准入和发布。
来源与全部转移在同一事务提交；校验失败或响应超过交付限制时不留下半完成状态。
验证 FAIL 可保留来源结果，但不晋升。未声明范围时返回 `KEPT_AS_OBSERVATION`。

相同已完成请求可核对为幂等结果；响应不明时仍先检查 operation 状态与候选 head，
不自动重发。撤回或被替代的经验不能借重试重新激活。事件保存策略身份、摘要和自动化
principal；这表示按授权策略完成核验，不证明实际采纳或因果收益。取消作业或移除
策略可停止后续调用；已经发布的经验通过原有撤回流程处理。

这个入口属于可信管理通道，消费端 MCP 不获得自动晋升、策略修改或发布能力。

## 先走通一个完整示例

在已按快速开始启动自己的数据库后执行。示例只核验一个固定文件
契约，明确标记 `synthetic_or_test_fixture`；它不证明真实工程收益或 Agent 来源。
需要公开安装的 Core 和 `pytest==9.1.1`，无需模型。

```sh
.venv/bin/python -m pip install pytest==9.1.1
# 用独立 profile 和专用示例 graph；按实际实例修改 DB 端口和密码文件引用。
.venv/bin/python -I -m aevora configure --port 17790 --graph aevora_demo_project_source \
  --password-file "$HOME/.config/aevora/local/falkordb.password" \
  --output "$HOME/.config/aevora-demo/host.json" \
  --session-root "$HOME/.local/state/aevora/demo"
.venv/bin/python -I -m aevora --config "$HOME/.config/aevora-demo/host.json" init
export AEVORA_PROJECT_DEMO_OUTPUT="$(mktemp -d /tmp/aevora-project-demo-XXXXXX)/result"
.venv/bin/python -I aevora_core/examples/project_source/walkthrough.py \
  --config "$HOME/.config/aevora-demo/host.json" \
  --output "$AEVORA_PROJECT_DEMO_OUTPUT"
```

脚本执行真实独立 pytest、来源导入、待核验/准入/发布和新 Run 查询。输出
`RESULT.json`、原始 JUnit、每步 CLI 输出和来源 receipt；成功时
`next_run_decision` 为 APPLY。示例通过公共 Python service 提议，不调用模型或
冒充一次真实 MCP/原生 Agent 执行。它只写这个专用示例图，不自动切换 Console。
已有示例 profile 时直接复用，无需再次 configure；普通项目的默认 profile 不变。

## 1. 确定三个角色

| 角色 | 可做什么 | 必须控制的输入 |
|---|---|---|
| 项目 Agent | 查询、提议候选、报告自己的观察 | 所属 Run scoped MCP |
| 独立验证作业 | 针对冻结提交执行受控测试，记录退出状态、事实与产物 | 候选不能修改的测试、runner、配置和产物写入位置 |
| Host / 项目负责人 | 授权可信作业产物、核验来源、审核范围、发布 | DB 凭据、来源策略、可信传输渠道和 review 身份 |

独立验证可由自己的受保护 CI 作业或单独控制的本地验证环境提供。必须核对
作业来源、提交身份、测试与 runner 的固定版本，确保它实际检查了所声明的
提交，并且事实由该作业测量或由 Host 独立建立。候选提交里的测试、脚本、
pytest 配置、插件和自报结果不能替换受控验证器。不在持有 Host 凭据的进程
中执行不可信候选；实际执行隔离由验证平台负责。

**信任入口是 Host 从独立渠道授权的 receipt SHA256。** 不要从 Agent 返回的
目录现场计算摘要，再把这个摘要当成独立来源。随包的 checksum 文件也不建立
信任。当前适配器核对已授权的本地产物，不验证 GitHub 身份、签名、远程作业
状态或运行时测量；这些属于所选验证渠道的接入职责。

## 2. 为自己的验证器配置 Host 策略

Host 在候选不能修改的位置保存 `policy.json`，目录 0700、文件 0600。
这是可重复使用的公开来源契约，不是凭据。字段如下：

```json
{
  "schema_version": "aevora.project-source-policy/1",
  "verifier_id": "my-project-independent-ci",
  "origin": "independent_project",
  "suite_sha256": "替换为已审查的完整测试集产物 SHA256",
  "evaluator_sha256": "替换为已审查的 runner 与配置产物 SHA256",
  "required_tests": ["test_receipts::test_idempotency", "test_receipts::test_parallel_flush"],
  "facts": {"concurrency_scope": "independent_processes", "shared_state_kind": "sqlite_file"}
}
```

上面的测试身份和事实是格式示意，应替换为自己验证器真正覆盖的内容。
测试身份采用 JUnit 的完整 `classname::name`，包括参数化后缀；必要集合
由受控测试定义预先固定，不从候选报告反推。只收录有证据的事实；未建立的
事实保持未知。测试集、runner、依赖与配置可各自打包成确定性的单个产物，
策略中的摘要固定其完整内容，CI 必须使用与这些产物一致的执行环境。

## 3. 独立作业生成来源包

Host先把原生`aevora inspect ID`的结果和已审查策略交给验证作业；Python对照使用`inspect --candidate ID`。
验证器取得同一 Run/候选对应的冻结提交，执行自己的必要测试并生成 JUnit。
停止 writer 后，在该可信作业中运行公开打包器：

```sh
python -I -m aevora.project_receipt \
  --candidate-file "$CANDIDATE_INSPECTION" --policy "$HOST_POLICY" \
  --submission "$EVALUATED_SUBMISSION" --suite "$TRUSTED_SUITE_ARTIFACT" \
  --evaluator "$TRUSTED_RUNNER_ARTIFACT" --junit "$ACTUAL_JUNIT" \
  --exit-code "$ACTUAL_PROCESS_EXIT_CODE" \
  --started-at "$ACTUAL_STARTED_AT" --ended-at "$ACTUAL_ENDED_AT" \
  --output "$FRESH_EXTERNAL_EVIDENCE_DIRECTORY"
```

这些变量均来自该验证作业，时间为带时区的 ISO 8601。策略文件也需满足
0700/0600。打包器只复制普通文件和记录实际调用方提供的作业结果，不执行
测试，也不赋予信任；输出状态为 `PACKAGED_NOT_AUTHORIZED`。
经受信任的作业通道取得它打印的 `receipt_sha256`，由 Host 决定是否授权。

包中 `receipt.json` 使用 `aevora.project-source-receipt/1`，绑定候选 ID、
提议体摘要、Run、verifier、origin、facts、实际起止时间/exit，以及
submission/suite/evaluator/JUnit 四个文件引用和摘要。不接受调用方传入
`verified` 或 `verdict`。引用必须为包内相对路径；符号链接、硬链接、穿越、
超限和摘要不匹配均拒绝。单文件上限依次为 32/8/1/8 MiB，receipt 为 256 KiB。

## 4. 为已有候选核验、审批与发布

以下均在 Host 的已配置 DB 环境中执行。变量使用自己真实候选和已授权来源：

```sh
export AEVORA_CANDIDATE='candidate:自己的run:自己的候选key'
export AEVORA_HOST_PRINCIPAL='project-owner'
# 新建仓库外 Host 工作目录；不放入候选可写位置。
export AEVORA_HOST_STATE="$(mktemp -d /tmp/aevora-host-review-XXXXXX)"
umask 077
.venv/bin/python -I -m aevora inspect --candidate "$AEVORA_CANDIDATE" \
  > "$AEVORA_HOST_STATE/inspect.json"
```

阅读提议体、当前状态和 `next_steps`。每次 review 必须携带刚检查的 head 摘要，
以拒绝过时审批；下面的辅助函数只提取这个比较值：

```sh
aevora_head() {
  .venv/bin/python -c 'import json,sys; print(json.load(open(sys.argv[1]))["head_sha256"])' \
    "$AEVORA_HOST_STATE/inspect.json"
}
```

如果仍是 PROPOSED，转入待核验；已经 EVIDENCE_PENDING 就直接导入来源：

```sh
.venv/bin/python -I -m aevora review --candidate "$AEVORA_CANDIDATE" \
  --state EVIDENCE_PENDING --expected-head "$(aevora_head)" --event-key begin-verification \
  --principal "$AEVORA_HOST_PRINCIPAL" --reason '等待独立项目验证'

.venv/bin/python -I -m aevora source-project --candidate "$AEVORA_CANDIDATE" \
  --policy "$HOST_POLICY" --evidence-root "$AUTHORIZED_EVIDENCE_DIRECTORY" \
  --receipt-sha256 "$AUTHORIZED_RECEIPT_SHA256" > "$AEVORA_HOST_STATE/source.json"
```

只有退出码 0、完整且唯一的必要测试集合、所有测试 PASS 才产生 PASS。
有效业务失败保留 FAIL，其他完整但非通过的执行保留 ERROR；缺失/矛盾证据
拒绝导入且不写图。`SOURCE_VERIFIED` 只表示来源核验完成，应同时检查
`outcome_verdict`；只有 PASS 可继续。导入不会自动审批或发布。

Host 将核准的事实范围写入 `$AEVORA_HOST_STATE/scope.json`：

```json
{"concurrency_scope":["independent_processes"],"shared_state_kind":["sqlite_file"]}
```

范围必须由独立事实证明，覆盖提议的必要条件，且不能扩大提议 scope；
触发排除条件、必要事实未知、跨 Run 或非 PASS 均阻断准入。然后执行：

```sh
AEVORA_SOURCE_ID=$(.venv/bin/python -c 'import json,sys; print(json.load(open(sys.argv[1]))["source"]["id"])' "$AEVORA_HOST_STATE/source.json")
.venv/bin/python -I -m aevora inspect --candidate "$AEVORA_CANDIDATE" > "$AEVORA_HOST_STATE/inspect.json"
.venv/bin/python -I -m aevora review --candidate "$AEVORA_CANDIDATE" \
  --state ADMITTED_BOUNDED --source "$AEVORA_SOURCE_ID" --scope "$AEVORA_HOST_STATE/scope.json" \
  --expected-head "$(aevora_head)" --event-key admit-project-scope \
  --principal "$AEVORA_HOST_PRINCIPAL" --reason '已核验来源并审核有界事实范围'

.venv/bin/python -I -m aevora inspect --candidate "$AEVORA_CANDIDATE" > "$AEVORA_HOST_STATE/inspect.json"
.venv/bin/python -I -m aevora review --candidate "$AEVORA_CANDIDATE" \
  --state PUBLISHED --expected-head "$(aevora_head)" --event-key publish-project-scope \
  --principal "$AEVORA_HOST_PRINCIPAL" --reason '发布已审批的有界经验' \
  > "$AEVORA_HOST_STATE/publication.json"
```

`review` grant原生默认10分钟、Python对照默认300秒，最多一小时；它授权Host操作，不是Agent工具。
重复导入同一来源幂等；CLI 审批以相同请求重试，修改内容要使用新的 event key。
中途停在 PUBLISHING 时，重新 inspect 并以当前 head 重试 PUBLISHED，或撤回。
每条写入独立完成，不保证全局事务；旧来源与失败报告不改写。

## 5. 在下一次任务中查询

回到实际项目的 graph 配置。用新 Run 启动 MCP，Host 上下文应记录新任务中
独立已知的事实；然后调用 `resolve_experience` 和 `build_evidence_bundle`。
也可先从 Host 验证同一条公共查询路径：

```sh
.venv/bin/python -I -m aevora query --run-id next-project-task --context "$NEXT_TASK_CONTEXT"
```

按 `publication.json` 中的 `experience_id` 定位返回候选，查看规则、支持链和
来源。如果上下文满足已证明的完整范围，可返回 APPLY；缺事实为 VERIFY，
冲突或反例可为 ABSTAIN。不要通过补造上下文强求 APPLY。PUBLISHING、撤回
和未发布候选不会作为有效已发布经验进入推荐。查询不证明采纳，收益保持 UNKNOWN。

## 每个状态的下一步

| 状态 | 下一步 |
|---|---|
| PROPOSED | Host 阅读不可变提议；进入 EVIDENCE_PENDING 或 REJECTED |
| EVIDENCE_PENDING | 独立验证 → source-project → 检查 PASS → 审核范围并 ADMITTED_BOUNDED |
| ADMITTED_BOUNDED | 以已检查的 head 执行 PUBLISHED |
| PUBLISHING | inspect 后重试完成同一发布，或 WITHDRAWN；此时不推荐 |
| PUBLISHED | 新 Run 查询、检查证据；必要时 WITHDRAWN/SUPERSEDED |
| REJECTED | 保留拒绝历史，用新 candidate key 提出修正候选 |
| WITHDRAWN | 保留历史；新证据经新候选重新审核 |
| SUPERSEDED | 保留旧历史，查询已独立发布的替代经验 |

没有独立验证器时保持 EVIDENCE_PENDING。适配器不把自测变成可信结果，
也不替用户证明验证平台的隔离或真实性。

契约实现：[来源适配器](../aevora_core/src/aevora/project_source.py)、
[打包器](../aevora_core/src/aevora/project_receipt.py)。设计参考
[pytest JUnit 输出](https://docs.pytest.org/en/stable/how-to/output.html#creating-junitxml-format-files)、
[Python XML 安全](https://docs.python.org/3.12/library/xml.html#xml-vulnerabilities)。
