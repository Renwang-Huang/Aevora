# 任务检索配置与质量边界

原生默认使用 SQLite FTS5/BM25、中文片段和受控工程别名，不需要其他服务。
任务描述只参与相关性；WHEN/WHY、发布/撤回与独立来源校验保留原权威边界。

词法候选先经过 `lexical-concept-coverage/1`，再按 BM25 排序和分页。候选至少匹配
60% 的去重查询词组（向上取整，最多64组）；受控别名组整体只计一次，同一组的
多个同义词不会增加票数。显式别名锚点仍按原规则必须同时满足。匹配继续由
SQLite 的 Porter/unicode61 分词完成；调用者提供的 FTS 操作符只作为普通词处理。
过滤发生在分页之前，不会先裁剪 top-k 再过滤而丢失后面的合格记录。

未知中文片段无法在词法层翻译：混合查询中保留为召回线索，但不计为独立门槛票数；
纯中文且没有已知别名时按中文片段匹配。响应中的 `lexical_coverage` 披露版本、
词组数、最低匹配数和截断状态。它也用于 ranked 观察检索，观察仍不可信。
该门槛只作用于词法通道，不是可答性分类器、适用性事实或成功概率。
关键词相同但操作不同仍可能误召回，长描述、改述与跨语言任务也可能漏召回。

## 可选本地语义通道

受保护 v2 Host profile 可添加 `retrieval`。使用已经安装的本地 Ollama 嵌入模型，
不会自动下载模型、启动服务或切换模型。配置示例中的模型必须改为实际本地模型：

```json
{
  "retrieval": {
    "endpoint": "http://127.0.0.1:11434/api/embed",
    "model": "your-local-embedding-model:tag",
    "min_similarity": 0.7,
    "max_documents": 2000,
    "timeout_ms": 15000
  }
}
```

这是现有 profile 的附加字段，database/session/console 保留原值。endpoint 只允许
显式 IP 回环地址的 HTTP `/api/embed`，不使用环境代理、重定向或凭据。协议复用
[Ollama /api/embed](https://docs.ollama.com/api/embed)，只发送 Query 的公开任务文本
和经验标题、公开摘要、策略摘录；来源路径、原始证据、条件和其他载荷不参与嵌入。
模型返回标识必须与配置相同。模型 tag 是受保护选择，不是模型权重的独立证明。

每次最多扫描配置的公开经验叙述（1..4096），每文档最多 2000 字符，每批最多16条，
维度最多2048，总调用受 timeout_ms（100..30000）限制。不足、截断、耗时与命中文档缓存
在 retrieval metadata 中可见。模型服务响应无效、超时或不可用时
`semantic_recall=UNAVAILABLE`，该次使用明确的词法降级；未配置为 DISABLED，成功为 READY。

语义余弦通道先按配置阈值筛选；词法与语义分别取最多50条，以
[RRF](https://learn.microsoft.com/en-us/azure/search/hybrid-search-ranking) 合并。
只有语义命中也能进入候选，最终仍重新读取经验并检查当前生命周期和固定事实。
语义独有命中不受词法覆盖门槛约束；配置的余弦阈值也不证明任务可答。
相似度、RRF 排名与阈值均不表示工程成功概率。完整观察检索的 ranked 模式目前仍是词法，
保持 UNTRUSTED；不会因模型相似就升级为经验。

嵌入请求在 SQLite 写事务之外；多个 Run 共享数据库时不会因模型延迟占住 writer。
文档向量缓存按公开叙述内容寻址，进程内、最多32MiB向量数据、5分钟有效，可丢弃重建，
不改变图格式/备份。重启丢弃；配置模型变化需重启 Host。新经验在下一次扫描进入；
撤回经验不能依赖缓存绕过当前发布检查。服务替换同一 tag 的权重后应重启清除缓存。

## 预算、容量与评估

默认结构化摘要规范 JSON 不超过32768字节，最多5张卡片，可选1..20。
摘要还按结构化 JSON、文本兼容表示和字符转义估算128KiB传输预算，超出则继续裁剪；
被省略身份不获得该 Query 的关联权限。完整 MCP 输出还包含信封，实际字节由官方 SDK 的预算门禁检查；
不能将摘要字节数当成 token 数。完整证据是按 Query 身份显式另取。

开发回归与容量基准可验证匹配、边界、延迟、分配和失败行为；合成向量服务只能证明
协议与融合正确。真实模型在真实任务上的 Recall@k、MRR、无关召回、token 成本和实际收益
必须独立评估，不能从这些测试宣称已补齐全部前沿语义质量。

固定质量语料、评分与基线边界见 [RETRIEVAL_QUALITY](RETRIEVAL_QUALITY.md)。

## 可选本地交叉编码重排

v2 Host profile 可独立增加 `reranker`，在现有词法/可选嵌入候选之后复用
[Hugging Face TEI `/rerank`](https://huggingface.co/docs/text-embeddings-inference/quick_tour)。
不会自动启动服务或下载模型，普通安装仍为一个原生二进制。示例中的模型和固定
revision 必须替换为已部署服务实际返回的公开模型 ID 与提交摘要：

```json
{
  "reranker": {
    "endpoint": "http://127.0.0.1:8080/rerank",
    "model": "your-public-org/your-reranker",
    "revision": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    "min_score": 0.0,
    "max_candidates": 32,
    "timeout_ms": 3000,
    "on_failure": "ABSTAIN"
  }
}
```

阈值必须显式提供，应在另立开发语料上按固定模型评估，不能照搬示例或用冻结挑战
标签调参。发送 `raw_scores=true`，不对当前候选做 min/max 或 softmax 归一化；原始
分数不是成功概率。全部低于阈值会保留空结果，不回退到被拒绝的词法命中。

仅允许显式回环 IP 的 HTTP，无代理、重定向、凭据和环境密钥。只发送公开任务文本
及最多64条已召回经验的标题/摘要/策略，每条最多2000字符，总请求最多1MiB。
不发送条件、来源引用或完整证据。HTTP 在 SQLite 写事务外，每个 Host 的适配器
最多一个进行中的请求，等待和3次请求共同受100..30000ms期限约束。

调用前后 `/info` 的 model_id、model_sha 与模型类型必须匹配配置。此身份是服务报告，
不证明磁盘权重；缺少提交、模型变化、非有限分数、重复/缺失/越界索引、超时或无效
响应均明确为 UNAVAILABLE。`on_failure=ABSTAIN`返回空候选；显式
`PRE_RERANK_FALLBACK`保留原召回通道，响应披露降级。没有候选时不调用模型，状态
为 NOT_RUN_NO_CANDIDATES。模型状态、固定身份、候选截断、输入裁剪和拒绝数可见。

重排只处理现有候选，不解决召回池之外的跨语言漏召回，也不产生可信事实、采纳或
Outcome。返回后仍重新读取经验，检查当前发布状态、作用域和证据。相同操作回放
复用原结果，不再次调用服务。离线 CLI 和多 Run Host 使用同一受保护配置路径。
当前协议/集成检查使用确定性测试服务；未执行真实重排模型质量对照。
