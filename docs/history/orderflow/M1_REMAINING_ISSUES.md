# M1 Remaining Issues and Boundaries

此清单以本轮实际观察为依据。三次Pilot已结束，原闭环1/3；本清单保留真实未解决条件，Overall CONDITIONAL PASS。

| 项目 | 当前证据 / 影响 | 后续需验证或实现的工作 |
|---|---|---|
| 完全敌对 Participant 安全 | 实际文件/网络边界探测通过；namespace 非 VM，进程内 SQLite 观测可被原生/opaque 路径绕过 | 扩展威胁模型与单独红队/VM级隔离；本轮没有该证明 |
| CPU 与输出硬上限 | D memory/pids 实际cgroup门禁；CPU controller未委派，聚合监控/RLIMIT保留检测窗口 | 有CPU委派环境下验证内核聚合限额；不能将当前采样描述成完全内核保证 |
| 恢复观察 API 范围 | 常用Python SQLite APIs / auxiliary/read-only / SQL/context / compensated多阶段实际正反控；native unbound C路径技术ERROR | 扩大通用观察支持或其他可信提交边界，不将未知恢复点改成PASS/业务FAIL |
| 模型服务等待与重试 | 三轮77/89/82请求，第一/三轮wall1200结束，第二轮完成；第三轮Test Engineer有429 retry-exhausted异常回执 | 根据实际请求区间分别衡量网络等待、任务诊断与协作开销；不在冻结三Trial中调预算 |
| 超时没有自动正式Submission | 第一/三轮原Run TIMEOUT/NOT_RUN；原样残留补丁在两个独立Run各28PASS，tree匹配；原自动仅1/3 | 可在后续授权阶段审查超时产物采集政策；离线通过不能替代本轮原自动结果 |
| 部分原始子任务正文不可读取 | 官方native通信元数据、加密任务body、子Agent自己活动/完成/回传可以分别观察 | 保持task_content UNAVAILABLE；不破解/猜测文本，不把自然语言声称当spawn证据 |
| 本地证据来源与不可变性 | SHA256和受保护历史比对支持本机可追溯；没有第三方签名/远程只读存证 | 后续建立独立存证/封存权限；当前不承诺抵抗维护者修改 |
| 难度统计与成本 | 三独立新Session，同配置有限预算；原自动1/3但三个代码样本通过Oracle，可能有任务天花板；usage可用、无账单 | 不作统计显著性/模型优越/治理收益结论；价格或真实收费保持UNAVAILABLE |
| 任务分布覆盖 | D v01为共享单机SQLite扩容/崩溃场景，2/4 Worker和多参数为稳健性覆盖 | 新故障变体需新因果机制/证据条件和独立准入；没有云集群/独立远端DB |
| 数据与归档体积 | 失败cohort、完整拓扑快照、原始日志全部保留；本轮约数GB | 后续优化快照引用/压缩/归档政策，不能删除失败记录制造干净结果 |
| 信息不足经验标签 | VERIFY为私有REFERENCE-ONLY设计条件；实际APPLY/ABSTAIN对照有来源与运行证明 | 没有第三正式信息不足Variant、检索或决策算法 |
| 未来系统 | B/C、完整支付与异步事件、GraphSwarm、FalkorDB/MCP、治理算法、G0–G3均未实现 | 仅在下一轮明确授权后推进 |

## 已完成与仍不能证明

三次原始状态、612条native事件、两次独立postmortem及逐文件提交保真已核对。post-pilot-preseal实际退出0，38,640历史/136冻结源无变化；最终再次检查并保存[FINAL_SEAL_SUMMARY.json](m1_validation/20261010T101602Z-8dfa7d4f-3c6c-4f4c-ac5a-57a06afa3e9e/FINAL_SEAL_SUMMARY.json)及[SEAL_OUTPUTS_SHA256.json](m1_validation/20261010T101602Z-8dfa7d4f-3c6c-4f4c-ac5a-57a06afa3e9e/SEAL_OUTPUTS_SHA256.json)。

仍不能证明完全敌对安全、内核聚合CPU强制、unsupported/native观察、初始加密task正文、底层模型权重、账单费用、第三方不可变存证或稳定统计难度/治理效益。Pilot原自动1/3，后续任务可审查429/网络重试、协作收尾和超时提交政策，本轮不改冻结三Trial或原成绩。代码样本通过不保证研究难度足够。

第一轮离线复测实际在12:14:30–12:15:07 UTC与第二轮联网挑战重叠。三个联网Session仍是顺序启动，但宿主并非全程空载；不能据此作精确延迟或纯任务难度归因。

完成M1后停止，以上限制不是自动推进下一阶段授权。
