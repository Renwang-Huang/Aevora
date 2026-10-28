# 检索质量基线

`go-runtime/internal/storage/testdata/retrieval-quality.json` 是调优前固定的公开合成标注，
含 10 类工程主题、60 条查询，development / heldout 各 30，分别含 10 条无答案。
它测相关性，不赋予适用性、来源信任或工程成功概率。

从 go-runtime 运行 `go test ./internal/storage -run TestRetrievalQualityBaseline -count=1 -v`。
可指定 `AEVORA_QUALITY_REPORT` 为新的仓库外文件，输出不会覆盖已有报告。
报告包含 Recall@5、MRR、nDCG、无答案误召回、延迟与实际返回 ID JSON 字节数。
该字节数不包含完整经验载荷，也不是 token 或完整协议流量。

同时报告 FTS5/BM25 和大小写不敏感、全部空格分词必须出现的字面文件搜索。
此简单对照不代表所有文件搜索产品。没有真实嵌入模型时明确记未运行，
不使用模拟向量推断语义质量。作用域与撤回门禁由独立领域/整合测试校验。

该版本标签在检索改动前提交固定；heldout 不用于别名、阈值或提示词调参。
真实任务语料应另立版本并保留来源，不混入私有评测真值。
初始得分是基线，质量差应保留，不通过降低标签要求获得通过。

`lexical-concept-coverage/1` 的回归保留上述语料和全部标签不变，比较同一 SQLite
查询路径的前后结果。公开标签已在复盘中暴露，旧 heldout 只作为固定回归集，不能再
称为新盲测。报告包含实际策略版本；门槛是固定 60% 查询词组规则，不依据 BM25
绝对值或该语料 ID 调参。独立机制检查覆盖同义词计票、Porter 词干、操作符字面化和
先过滤后分页。小语料误召回归零不代表真实任务可答性问题已解决。

`testdata/retrieval-challenge.json` 增加16份工程主题叙述和50条邻近任务查询，含16条
无答案和一个多答案任务。它在覆盖策略固定后单独提交，后续不使用这些标签反向调整
该策略；仍是人工公开合成语料，不是盲测或真实用户收益。运行
`go test ./internal/storage -run TestRetrievalQualityChallenge -count=1 -v`，可设置新的
`AEVORA_QUALITY_CHALLENGE_REPORT` 输出文件。多答案 Recall 按完整相关集合计分，
nDCG 使用二元相关性和理想排序，重复 ID 不重复得分。

该挑战集明确保留词汇高度重合但操作不同的失败案例。它与旧集分别报告，不把两个
集合平均后掩盖困难任务；简单字面搜索的高精确、低召回也一并保留。后续可在新任务
语料上比较本地嵌入、交叉编码重排和词法通道，仍需同预算、独立模型身份与失败记录。
