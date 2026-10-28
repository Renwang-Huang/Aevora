# 原生用户运行时

Go运行时提供受限MCP接入和可信Host生命周期。Go领域服务已接入SQLite事务边界，
保留Python Worker/Core/FalkorDB作为过渡对照；综合验收完成前不切换main。
原生CLI通过v2 profile选择Go/SQLite，v1 profile保留旧引擎对照。
领域与存储的替换保持传输、授权和结果契约。

Go领域包含适用性/治理投影、实际证据路径、不可变Query/Snapshot、Decision、
Candidate、受保护Host policy下的项目receipt/JUnit核验、发布/撤回与观察反馈。
反馈仅形成OBSERVED_OUTCOME，不提升为采纳、正向支持或因果收益。原子业务操作
与内部operation结果在同一SQLite事务提交；网络响应与审计送达仍分别记录。
新路径说明采用与后端无关的措辞，Python新查询同步使用；历史snapshot原字节保留。

业务参考包含生命周期返回前的可变head复查、发布重放的撤回检查和请求级分页预算。
Console对LifecycleHead的每次复查都重新读取数据库，不能被请求缓存替代。
Python canonical字节、摘要和公开字段样例由`tools/native_reference.py`生成到
`go-runtime/contracts/reference.json`；Go实现使用这些样例对照，不能自生成预期值。

原生存储采用`modernc.org/sqlite v1.61.0`，固定Go 1.27.3工具链；实际内嵌SQLite
版本由运行时探测并记录。本次Linux驱动比较中，modernc与ncruces均通过唯一/FK、
WAL读快照、新鲜head、锁等待、取消、VACUUM INTO备份及未提交事务强杀恢复检查。
选择modernc保持`database/sql`与标准context取消分类；ncruces作为对照候选，不引入
第二套生产后端。其他平台的原生存储验收仍待统一综合评测。

SQLite物理schema与逻辑记录schema分别版本化。原始canonical payload和摘要保持，
固定标签/关系、显式索引、外键和CAS保护领域记录，不实现Cypher翻译器。受控单写
连接与有界读池分开；可变head使用独立新鲜连接，避免读事务的旧快照和连接池饥饿。
数据文件本身参与OS排他与物理身份绑定，拒绝链接；不只锁session目录。
备份使用SQLite的`VACUUM INTO`一致性快照到新私有文件，失败不启用目标文件。

## 身份和所有权

一个受管本地 backend 绑定一个受保护 ownership root。backend 身份由精确的
旧引擎的`127.0.0.1:port/graph`定位，或SQLite数据文件的物理身份与随机backend UUID，
及用户级受保护注册表共同约束，不使用凭据或其摘要。
不支持远端地址、代理别名或跨用户共享 backend 的排他声明。注册绑定不可静默
改根；运行根不同不产生第二写权限。旧 Host/CLI/私有集成参与同一 backend guard。
所有权注册表固定在OS账户的本地状态目录，不随调用方HOME/XDG命名空间改变，
避免不同终端环境为同一backend各自创建一把锁。会话和配置位置仍可显式选择。
排他约束要求所有writer共享同一OS账户与注册表文件系统；隔离容器或不同主机
需要统一Host入口，不能据本地文件锁声明跨容器或分布式排他。

Host 构造不可由 consumer 提交的 RunContext，固定 backend、Workspace、Run、
facts、facts 来源/版本、能力与 policy。Agent 声明不建立可信 facts；UNKNOWN
不补齐。默认兼容同授权 Run 的 Query 共享，不支持跨 Workspace 重名授权。
Agent 原生身份未核验时记 UNKNOWN，Session 和连接身份另行记录。
Run的规范化上下文摘要由所选领域引擎产生，Host在受保护的`contexts/`中
独占保存绑定；重启不能改变同一Run的事实。旧Query历史也会有界核验，冲突或
超过4096条时要求使用新Run。`AEVORA_RUN_CONTEXT_CONFLICT`不会覆盖旧pin或事件。

## 接入和操作结果

stdio Bridge 只读取当前 selector/grant 并连接鉴权 IPC，不读取 Host profile。
受隔离客户端可使用`mcp-connect --grant`读取Host创建的单Run connector授权，
仅映射授权文件与命名空间socket，服务端仍独立校验Run/token及kernel peer。
Host 使用官方 Go MCP SDK，catalog 从实际 Python SDK 导出的契约读取；默认三个
工具，可显式启用 Proposal。管理操作不进入 consumer catalog。首个兼容协议为
2025-11-25，其他协议不自动启用。
当前官方客户端的`server/discover`预探测交给同一SDK处理，协商回已支持的
2025-11-25；不因客户端先探测新协议而直接断开连接。

Resolve 会创建 Query/Snapshot，属于有副作用操作。所有写入记录独立 operation
identity、请求绑定和状态：QUEUED、DISPATCHED、COMPLETED、FAILED_KNOWN、UNKNOWN。
派发意图先持久记录，写盘失败不执行；派发后断连、超时、Worker退出或输出超限
不证明未写入。未知结果不自动重放。同键异请求拒绝；账本状态不授予跨 Run 权限。
方法完成、响应送达和数据库持久化分别表达，不承诺 exactly-once。

Python Worker 仅经私有长度前缀 pipes 接收固定操作，不启动旧 MCP Broker，不
提供任意 shell/import/Cypher。每个执行槽串行，池和排队有界。Worker 持有 Host
锁的继承引用，Host 强杀后即使 Worker 尚未退出，也不能提前让出写权限。

## 资源和安全

保留总连接4、owner lifetime累计4096协议帧、消息262144字节（包含换行）、
深度16/节点20000、认证头4096字节/10秒、请求60秒（配置上限120秒）的界限。
所有Session共享预算；慢读、审计、排队和输出有界。新连接不复位预算。
输入输出拒绝重复键、非有限数、非法UTF-8及超限形状。审计仅记录授权与状态
元数据，不保存token、秘密、原始自由文本或其单独摘要。
原生SQLite在提交业务记录前，按官方SDK实际编码的结构化结果、完整JSON文本及
协议封装共同校验262144字节上限；超限回滚并返回AEVORA_RESULT_BOUND_EXCEEDED。
保留完整证据和数值身份，不截断为AVAILABLE。显式Python参考Worker仍采用64KiB
结果上限，其超限状态保持UNKNOWN。

文件目录和grant必须是所属用户的受保护普通文件，拒绝链接。平台实现未提供
peer/锁/进程约束时拒绝启动，不匿名回退。Linux采用UDS/SO_PEERCRED和flock；
其他平台的构建成功不等于已通过原生运行验证。本地同UID不是敌对程序沙箱。
Unix会话路径超出UDS长度时，仅socket放入固定OS账户的私有短运行目录；metadata、
事件和授权仍保留原session root。短地址由会话目录摘要派生，验证0700所有权与peer，
不受HOME/XDG覆盖；正常关闭只移除该socket及其空子目录，不删除持久证据。

Console通过Go标准net/http内置到同一二进制，`serve`绑定配置的loopback端口并输出URL。
`demo`不需要项目配置，显示内置独立pin的PUBLIC Replay。前端仍复用现有界面；Node
只用于维护者构建静态资源。`tools/native_assets.py`同步明确allowlist的构建产物和历史
artifact原字节，并记录来源摘要；`--check`拒绝漂移。Go启动校验内置资源和Replay pin，
运行时不执行Python verifier。Replay投影的5个案例/状态由现有Python实现生成独立摘要。

Console依旧只读；Go运行时发布兼容旧Console的session selector与事件头，额外
operation审计为独立版本，不伪造旧SDK原始事件。真实图断连不回退Replay。
HTTP只允许GET及明确资源，检查Host/Origin，连接上限16、并发读取4、请求10秒、响应
8MiB。SQLite分页使用稳定ID和绑定Run/Experience的cursor；读取及领域内校验共用
500节点、1200边、8MiB payload和4096查询预算，超限失败而不伪造可用结果。
运行时metadata最多读取每个受管Run的128KiB前缀，明确标注未完整读取，不建立Agent身份。

## 开发和集成

原生迁移使用停写窗口下的逻辑导出，不解析RDB，不双写：维护者在匹配的旧Python
环境执行`python -m tools.export_native --config OLD_PROFILE --contexts CONTEXTS.json
--output NEW_EXPORT`。contexts是独立批准的公开facts列表，1..32项；导出器持有现有
backend的排他barrier，导出前后核对全图指纹并保留canonical payload原字节与摘要。
未升级、不遵守barrier的writer必须事先停止。源schema须显式升级到当前逻辑版本。

使用输出的独立manifest pin创建新项目：

```sh
aevora --config /absolute/new/host.json import --input /absolute/export --sha256 MANIFEST_PIN --data-dir /absolute/new/data
aevora --config /absolute/current/host.json backup --output /absolute/private/backup.db
aevora --config /absolute/restored/host.json restore --input /absolute/private/backup.db --sha256 BACKUP_PIN --data-dir /absolute/restored/data
```

import/restore要求新的data目录和profile，核对完成才生成profile；失败目标保留，
不自动重试或启用。导入核对文件pin、原始记录字节/摘要、稳定ID、全部关系、节点/边
数量、源图独立指纹、生命周期、已声明的历史snapshot关联和源resolver业务witness。
缺少snapshot证明的旧版本历史保持原字节并明确计数，不重建或提升其权限。
restore核对独立SQLite备份pin、实际DDL、schema版本、完整性、外键和领域历史；
备份必须是关闭的独立文件，拒绝伴随WAL/SHM/journal的输入。当前文件上限512MiB，
逻辑导出每个节点/边文件64MiB，最多100000节点/200000边；超限失败关闭。
目标生成新的backend身份和授权；原有Run历史只读，使用新Run继续。旧库和旧配置
保留为回滚来源；切换后已有新写入时须另做反向数据审计，不能直接回退丢弃增量。
不提供删除项目数据的uninstall命令；替换二进制或升级不会隐式重建/降级schema。
新版本schema、实际DDL不符或损坏文件拒绝打开，不执行自动修复。

契约位于 `go-runtime/contracts/`，生成器为 `tools/runtime_contracts.py`。
从当前Core及其固定Python SDK生成，`--check`拒绝漂移，不触发数据库或模型。
真实数据库、目标客户端、原生平台与故障恢复在整合测试单独报告。
开发分支按职责命名并依赖叠放，整合验收前不合入main；不把阶段编号用于模块、
命令、配置字段或测试身份。构建缓存、venv、数据库与验证输出保存在仓库外。

成熟实现依据：[官方MCP Go SDK](https://github.com/modelcontextprotocol/go-sdk)、
[Cobra](https://github.com/spf13/cobra)、[go-winio](https://github.com/microsoft/go-winio)。
锁定依赖和工具链，不实现另一套MCP协议或Agent调度器。

## 使用当前开发版本

Go模块固定工具链和SDK；在 `go-runtime/` 中构建到仓库外：

```sh
go build -buildvcs=false -trimpath -o "$AEVORA_RUNTIME_OUTPUT/aevora" ./cmd/aevora
```

原生入口无需Python或数据库daemon：

```sh
aevora init
aevora serve --enable-proposals
aevora mcp-config
```

`init`只创建新的私有数据库和v2 profile，不覆盖已有项目。`query`、`inspect`、
`review`、`source-project`、`feedback`和`backup`通过独立可信管理通道调用Go领域。
Host运行时共用其写池；离线操作必须取得同一数据文件锁。管理token不进入consumer
grant或MCP工具。`open-run`可授权最多64个独立Run；`mcp-connect --run-id`读取该Run
selector，消费者不能选择新的facts。每个Run仍固定facts与能力，重启重新授权。

旧引擎对照环境先安装本checkout的公开 `aevora_core`。显式设置
`AEVORA_HOST_PYTHON` 为其解释器绝对路径；不自动安装或调用系统Python。
使用现有Python CLI完成数据库初始化并保存Host profile，然后用新程序：

```sh
aevora --config /absolute/private/host.json serve --enable-proposals
aevora --config /absolute/private/host.json mcp-config
```

生成的connector只接收稳定session root。Host必须先取得backend写权，两个
Worker都核验实际schema/约束和连接后才READY。当前受控backend只接受精确
127.0.0.1端点。需要旧CLI的review/source等管理操作时，先正常停止Go Host；
旧CLI也会取得同一写锁。所有旧写入口经Repository执行，不提供跳过guard的开关。
首次登记受管backend前必须停用未升级Core的旧writer；旧版本不认识新guard，
不能仅靠新二进制约束未升级程序或持有凭据直接调用SDK的程序。

运行时事件只含metadata，Console明确识别 `aevora.native_host` 来源，不伪装成
Python SDK原始JSONRPC。operation的COMPLETED与WRITTEN_TO_TRANSPORT分别记录；
后者只证明交给本地传输，不证明客户端消费。中断未得终态时保留UNKNOWN，
不自动重试或复用旧grant。完整整合、真实客户端与平台验收通过前不切默认入口。
杀死Worker不能撤销已发送给数据库的语句，UNKNOWN也可能伴随迟到的写入完成；
后续操作不能据超时推断旧操作没有执行。

原生`aevora doctor`检查数据库quick_check、外键、实际SQLite版本与schema，再通过
真实connector/官方SDK进行initialize/list-tools/ping，并检查配置端口的LIVE health
与backend身份。不执行resolver或模型；未连通的组件保持UNAVAILABLE，旧引擎只验证
配置前提。单独数据库diagnostics不主动探测其他组件，仍保持NOT_PROBED。
`aevora operation-status --session-directory PATH --operation-id ID`读取受保护
审计；派发后无终态返回UNKNOWN，只读查看不触发恢复或重放。

平台实现：Linux为UDS/SO_PEERCRED/flock，macOS为UDS/xucred/flock，Windows
复用go-winio Named Pipe，限制DACL、远端连接、peer用户及logon身份，文件采用
ACL/LockFileEx并拒绝reparse和硬链接。Windows当前只具备原生运行时适配，
明确拒绝启动POSIX Python Worker；真实Legacy业务先在Linux验收。
各目标交叉构建只证明BUILD_PASS，原生权限、进程与恢复仍需独立运行验收。
配置/状态默认目录遵守平台约定，显式XDG设置仍须为绝对路径。

构建显式关闭自动VCS stamping，以支持worktree和无.git的公开source包；来源
使用交付时记录的Git提交及文件清单。测试、缓存、二进制和报告不写入源码树。
