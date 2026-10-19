# Aevora Gen 2 / G2-0 审查入口

**Status: ARCHITECTURE_AND_CONTRACT_FREEZE_CANDIDATE, NOT_GEN2_IMPLEMENTED。** 以真实V5C.1 fc539c8524250b53af5353bfce13f1ee857b3695为parent，仅本目录新增设计/协议/合成探针合同和设计检查。生产Core、Runner、Evaluator及历史结果不变。完成后等待独立审查，不自动进入G2-1。

阅读顺序：

1. [基线与验证级别](00_BASELINE_AND_AUTHORITY.md)、[AS-IS源码审计](01_AS_IS_ARCHITECTURE_AUDIT.md)、[源码映射](SOURCE_ENTRYPOINT_MAP.csv)。
2. [最终架构](02_GEN2_FINAL_ARCHITECTURE.md)、[13项ADR](ARCHITECTURE_DECISIONS.md)。
3. [Graph v2](03_EXPERIENCE_GRAPH_V2_SCHEMA.md)、[Cypher合同](GRAPH_CYPHER_CONTRACTS.md)、[typed catalog](contracts/graph_v2_catalog.json)。
4. [生命周期/身份/Host合同](04_AGENT_LIFECYCLE_AND_TRUST_CONTRACT.md)、[MCP兼容](MCP_COMPATIBILITY_AND_VERSIONING.md)、[typed JSON schemas](contracts/mcp_v2.schema.json)。
5. [独立验收和对照](05_BENCHMARK_AND_CAUSAL_EVIDENCE_PLAN.md)、[四幕Evidence计划](HERO_STORYBOARD_AND_EVIDENCE_SHOTS.md)。
6. [开发顺序/发布](06_IMPLEMENTATION_AND_RELEASE_PLAN.md)、[公开私有边界](PUBLIC_PRIVATE_BOUNDARY.md)、[逐文件来源](HACKATHON_CONTRIBUTION_MATRIX.csv)、[Gate](GEN2_GATES_AND_DEPENDENCIES.csv)、[主张证据](CLAIM_TO_EVIDENCE_PLAN.csv)。

`contracts/examples.json`全是明确标记的合成协议形状，不是新Agent行为、真实Source或Outcome。ID示例只演示字段结构，实际存在性/确定性身份、context authority、canonicalSHA、权限和body语义仍需生产Host验证。`test_design_contracts.py`验证schema与合同文件一致性，不替代生产权限/图裁决/原1897项测试。

复核设计文件可使用Python3.12 + 已安装pytest/jsonschema：`python -m pytest -q docs/gen2/g20/test_design_contracts.py --junitxml=<FRESH_EXTERNAL>/JUNIT.xml -p no:cacheprovider`。真实执行环境/argv、当前SDK schema抽取、图探针、失败/回收收据及G20最终报告在独立Evidence目录；不可运行旧历史脚本向封存结果写入。

新协议示例MCP args应从schema读取：先`resolve_experience(task_context={})`，保留query/candidate/recommendation references；真实返回newID才Bundle，依据证据作自主claim；不强制APPLY/固定经验ID。源代码审查足以指导后续实现，不是新机制已PASS。
