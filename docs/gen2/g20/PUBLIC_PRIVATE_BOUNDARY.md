**Freeze candidate 2.0.0-rc1 — PROPOSED / NOT_RUN unless explicitly marked.** All real model trials below require the later Gate authorization. No Gen2 challenge runs or production implementation occur in G20.

# 公共、Participant、可信Host与维护者边界

| 资产 | 产品发布 | Participant | Host / Full | 约束 |
|---|---|---|---|---|
| aevora_core/src、公开Core docs/Receipt例子 | 现有allowlist候选，新增v2需检查 | 只能proxy/tool返回，不mount服务器/admin | 实际server字节pin | Core安装不得导Benchmark |
| console/src/web、批准h4 demo/Replay | 可审核public | 非工程Participant输入 | 保留原镜像/包/浏览器证据 | LIVE/REPLAY明确，不隐藏失联 |
| 新v2 schema/Cypher/公开synthetic例子 | G2-6审核后可公开 | 仅公开任务与工具schema，无期望答案 | 原始design/negative期待保留 | 本G20 docs默认维护者设计，未自动加public allowlist |
| app公开buggyfixture/Public Issue/Public tests | 单独Benchmark公开任务协议 | 当前Run可见 | 基线SHA/实际patch | 不共享前轮patch/rollout |
| benchmark/runner/submission、evaluator/Oracle/Reference/private manifest/labels | 不随产品公开 | 禁止 | 必须保留且独立调用 | 全回归/安全必须保留，不靠命名隔离 |
| Graph admin/password/Gateway key/HostGrant/旧native state | 禁止任何包/日志/单项secretSHA | 禁止，只有run-scope token proxy | 外部0600/0700 | no-follow读取，撤销scope，秘密值仅内存扫描 |
| Full原始Native/HTTP/MCP/Outcome/Graph数据库 | 不公开、不同tenant不可读 | 禁止 | 保存失败/原hash/权限 | 本地hash不等外部存证；sharedkernel限制披露 |
| Audit-Lite/公开Hero摘录 | 独立脱敏/权限/license后单独release | Audit材料不作Participant输入 | 原→导出逐文件/逐行SHA | 无Hidden Oracle/reference/privateDb；不静默删失败 |

现有tools/public_release.py::chosen是可运行权威，docs/gen2/g20不因Git跟踪自动发布。G2-6增加allowlist须逐文件审查、包成员/实际privatebyte/秘密值内存扫描、干净install与真SDK；不把此维护者仓库整体推私有GitHub再假设以后转public安全。

MCP无Host outcome/publication/arbitraryCypher工具；Graph物理tenant映射由可信服务固定。Native Runtime与业务命令两个层级隔离沿用原ParticipantSandbox/bubblewrap/cgroup；Host模型连接key不进入子shell。原生children继承权限，role指令不形成独立安全域。真实攻击探针覆盖Oracle/Reference/privateconfig/maintainersrc/otherruns/credentials，失败则禁Live，不降低沙箱换联网。

历史归档保留只读。新数据生命周期：owned runtime生成→Runner停止候选→独立Oracle→Host验证→graph追加→资源回收→Full seal→Full外Lite/negative/terminal receipts。不用临时历史映射把私有内容暴露给Participant。公开数据限public/synthetic/自有且授权的事实，不直接发布个人/私有graph。第三方license未明确时阻止该文件发布，保留待核，不假设本地拥有就能公开。
