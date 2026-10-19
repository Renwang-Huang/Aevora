# Aevora H4-G4 Differentiation Demo

**结论：PASS（真实机制与本地展示范围）**。普通工程外部测试仍为 EXTERNAL_UNVERIFIED，不升级可信Outcome。

## 新真实 Session

- Run `238caf3b-957f-4ae2-bb4a-8fc21a3c4c7f`；Session `01a133ea-cbf2-7872-9b55-c137ae5e3eb5`。
- 原始Runtime PASS、退出0，1065.023秒自然完成；27次Gateway请求完成，观察请求模型gpt-5.6-terra、max与配置一致；不证明模型权重。
- Source epoch `679c97a346c36f919f8b7185465dcda86ad172c6` / Tree `6f4a1bdc5b7bf1d22042fcf8772395aad886fa33`，即已准入的G1 epoch02。后续Console/文档提交不倒归给该模型Session。
- 实际补丁SHA256 `1251fae358b9f637281165422d069006b2fa0143f95dee77bce2b0594022fd90`，仅app/receipts.py；严格提交应用后实际独立隔离重放原7项公开测试，退出0/7PASS，测试源哈希未变。
- 一项实际AVAILABLE查询返回2候选；两项实际证据包及两项RECORDED_UNTRUSTED；原始2次resolve中第一次非规范输入失败，3次propose_experience均失败，保留原始MCP错误。没有宣称成功生成候选。
- 实际Graph检查该Run的VerifiedOutcome数量0；Host只记录ExternalObservation。原生模式为single；未将本轮冒充Multi-Agent运行。三名完整原生Subagent来自Case A的历史原始证据。

命令：`python -m scripts.aevora_h4_native run --label ordinary_repair_02`，通过已验证bubblewrap/Gateway/原生Codex adapter执行；实际argv、UTC、退出0与日志SHA见 `g4-native-ordinary-repair-02/command.json`。Runtime原始JSONL/native rollouts、Submission、public-tests、SourceEpoch和封存manifest均在 `g4/native/ordinary_repair_02/runs/238caf3b-957f-4ae2-bb4a-8fc21a3c4c7f/`。

## Console实时验收

Playwright实际观察8次当前状态/工具变化，最后捕获原始终态与Session ID；`g4/live-observation-03/RESULT.json` PASS，零pageerror，一次实际连接错误重试（服务受控重启）。截图与trace保留。Viewer状态来自真实typed header与完整MCP行，未由自然语言发明事件。快照时间与进程liveness UNAVAILABLE明确区分。

新增实际尾行文件协议检查：未完成尾行标PARTIAL，仅完整事件显示；完整畸形行仍fail closed。非公开工具名不会投影原始字符串。API/static/demo40项退出0，浏览器最新07仍17/17PASS。

## 三幕与差异控制

- `g4-fresh-replay-reader-01`：新复制公共读端独立verify +三幕CLI，退出0；额外3个实际LIVE上下文，无DB写入。
- `g4-actual-graph-necessity-02`：当前FalkorDB独立副本中实际删除同一VERIFIES边，支持1→0/APPLY→VERIFY，恢复后回到APPLY；历史QuerySnapshot哈希不变；原图指纹不变；副本移除。是真正Host受控干预，零AgentOutcome。
- `g4-portable-demo-tests`：2/2PASS，包括错误外部pin拒绝。
- 旧Governance/Raw原始成绩二者7/7仍保留；未重跑成收益统计或编造Raw失败。

操作与话术：`docs/DEMO_WALKTHROUGH.md`，视频未完成，提供`DEMO_RECORDING_GUIDE.md`。图不能证明Agent采纳或因果收益。公共浏览器不需要维护者口令。

## 失败与恢复

第一次新挑战Run81d8c54f-43c1-4cd8-8963-ce7f23534080在交互回合中断后没有终态收据，保留INCOMPLETE_COLLECTION、退出UNAVAILABLE，未评测/未升级成绩；实际根因UNVERIFIED。其原始pending数据与恢复的official rollout保留，已停止的临时Codex状态清理。第一次Viewer观察因连接重置PARTIAL。第二次Observer同样记录ECONNRESET；明确重连/关闭复用连接后第三次完成，所有失败仍在。

恢复工具的前三次尝试失败，原因是可信隔离内宿主原始secret路径不可见以及宿主Python3.10无StrEnum；使用原有可信挂载别名和实际Python3.12后成功，未扩大Participant权限。图控制第一次因误取Core原始字段support_paths而KeyError，保留日志；通过已有decision_view投影取实际principle_support_paths后通过，未放宽业务判据。

持久证据Owner复用标准subprocess执行一条现有命令，记录实际退出；不是Agent编排器。服务停止只终止其实际子进程，保留收据Owner以记录-15。Native取消仍由既有RuntimeControl负责。

G3首次源码提交未选中docs CSV；矩阵文件存在且本次G4源码选择已补入CSV，未修改原G3提交。源选择修正与实际矩阵SHA将进入当前交付，不把后续补充伪装成旧commit内容。
