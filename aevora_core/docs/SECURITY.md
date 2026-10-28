# 安全、生命周期与可信结果

Host 持有图凭据和管理能力。Agent 使用 scoped MCP 通道，只获所属 Run 的
公共上下文与允许工具。请求不能覆盖已固定事实，未知信息保持未知。

## 候选生命周期

```text
PROPOSED → EVIDENCE_PENDING → ADMITTED_BOUNDED → PUBLISHING → PUBLISHED
    ↓             ↓                  ↓              ↓           ↓
 REJECTED      REJECTED           WITHDRAWN       WITHDRAWN   WITHDRAWN/SUPERSEDED
```

提议体不可变，输入不能自行携带可信 authority、outcome 或 run 身份。
每个 head 转移用实际写入 fence 并追加事件/关系；stale 和冲突请求失败关闭。
发布的物化是可重试多查询工作，PUBLISHING 未完成时不进入 resolver。
有界重查不保证任意读路径的可串行化，全局事务不能从局部 fence 推断。

## 来源核验

OrderFlow Host verifier 使用已授权的 Run/source manifest pin、实际 JUnit
身份、patch-derived tree、suite/evaluator 指纹和独立 Oracle。当前原生
候选还需真实 MCP proposal request/reply、typed 工具完成与新 Session 来源。
调用方不能以 verified 标记或自报 PASS 替代这些证据。

普通项目的 `source-project` 使用单独的 Host 策略与经可信验证作业渠道授权的
receipt pin，核对同候选/提议体/Run、冻结提交、固定 suite/evaluator、完整
JUnit 身份和事实。`project_receipt` 只打包，不建立独立性。导入器不执行候选，
也不验证远程 CI 身份或签名；独立执行、隔离与可信传输是验证平台的契约。
来源明确为 independent_project 或 synthetic_or_test_fixture，不冒充 natural_agent_run。
完整步骤见[普通项目来源接入](../../docs/PROJECT_SOURCES.md)。

独立 PASS 可以支持有界事实范围的准入；不证明经验采纳或因果改善。
外部项目观察为 EXTERNAL_UNVERIFIED，不通过公共工具升级为可信结果。
重复语义保持幂等，冲突拒绝重新解释旧身份，新 verifier 版本需显式迁移。

## 通道与秘密

Owner 退出撤销 grant/socket。capability 目录属于当前用户且为 0700，
文件为 0600，不进入源码或归档。可显式设置 TTL，它与 Agent 总完成期限
不同。连接/查询有限等待，原始异常不泄露秘密或无界 traceback。

Host profile 只保存秘密文件引用和公开事实，受所属用户 0700/0600 保护，
不发给 Agent。connector 只读取当前 scoped grant，并移除继承的 DB 配置。
自动会话每次创建新目录与事件；内核锁阻止活动 Host 使用同一根重复启动。
正常停止撤销 grant/socket，崩溃后保留旧残留并创建新会话。稳定 selector 可替换，
不是证据；事件与 manifest 不覆盖。会话根可能残留 grant，不整体归档。

普通同 UID 开发通道不隔离敌对进程。部署必须保护 Host 账户和秘密目录，
不可信实验使用独立物理边界。cwd、编辑器视图或“只有 socket”配置不单独
证明沙箱。公开工具不提供 admin、原始 Cypher、审批或 Outcome 写入。

## 持久化与证明范围

RDB 恢复覆盖最后完成 SAVE 的边界；未保存 crash tail 不保证零丢失。
多语句追加、读快照、原生 UDS、资源采样、共享内核和 prompt injection
分别有边界。图管理员仍可改变数据库；本地摘要不是外部签名或不可变存证。
运行限制见[产品限制](../../docs/LIMITATIONS.md)。
