# Aevora H4 Final Local Release

**H4 Overall：CONDITIONAL PASS。G0–G5公共产品在本地授权范围PASS。**

正式入口：AEVORA_H4_VALIDATION_REPORT.md、AEVORA_H4_G5_RELEASE_REPORT.md、AEVORA_H4_TRACEABILITY_MATRIX.csv、AEVORA_H4_LIMITATIONS.md。1802/1802当前回归，原1714身份全保留；215589历史文件/79测试源/39真值/25旧报告无变化。

公开产品：`aevora_validation/H4-20261013T032951Z-7c8b693a-7f84-4e8b-b3c1-c2e9f37f48ef/g5/public-product-final/aevora-h4-public-source.zip`，SHA `fb282c5a7bbec8b6f90a16205d1683a1da7f9772c965f01066ae5bd9b86fbd03`，457304字节；独立公共Git commit `00c43f53ce8d2c04af956d6b88c601efc17dfa7b` / Tree `58cbeeab12598a9a7891a0104e81c4bfd944d567`。Core/Console各wheel/sdist在同目录dist/，真实安装/byte check通过；Docker final image65c4c308...，实际image.tar SHA a427ec51ac1440788427b14fbb5b67181916ad3eb9f0267ebaa5a695596b958d，镜像/root/HTTP安全扫描通过。公开部署命令在Quickstart与h4/deploy/README。

Raw native repair238caf... 7原公开测试PASS，EXTERNAL_UNVERIFIED/0VO；新empty readonly3c307... nativeexit0/观测PASS，原ERROR/NO_PATCH，19请求200，gpt-5.6-terra/max。不中断健康长运行，不将subagent配置或查询当作因果证明。

Full `aevora_validation/H4-20261013T032951Z-7c8b693a-7f84-4e8b-b3c1-c2e9f37f48ef`，Manifest `0fcb56a4c52ff5069dfbf8dccad23411759c14d269cadc32876ab752736368b2`；可独立逐文件核对SHA256SUMS。Audit-Lite v3 `aevora_validation/audit_exports/H4-20261013T032951Z-7c8b693a-7f84-4e8b-b3c1-c2e9f37f48ef/aevora-h4-audit-lite-v3.zip`，SHA `361b37b2cb9cbf2a8e55bea043b9d364ac0e091eb639b65e21c196a5f1a8dd97`，8.29MB。它是**MAINTAINER_AUDIT**，不能给Participant或公开产品。独立verifier可从受信的源码另取，`python3 -I independent-verifier.py verify aevora-h4-audit-lite-v3.zip --json`；本轮真实执行0，字节/重哈希成绩篡改均2，确定性导出相同，Full不变。

最终受控运行服务已停止，两个本轮独立数据卷保留；H1-H3服务和历史文件不被重置。本地Git release独立checkout提交，root index不stage，未推送Github/其他git托管，也未外网部署/官方提交/完成视频。录像指南与真实三幕Replay可复现；三幕是不同来源。

封存后新增导出选择修正、最终检查脚本和闭环文档是独立post-seal source commit；Full原/source/runtime版本不改。最终关联由outside-Full FINAL_DELIVERY_RECEIPT提供。完整限制仍看LIMITATIONS：共享内核/EOL、RDBlastSAVE/AOF139、D-v02UDS EPERM、agent采纳/因果收益/模型权重/实际费用UNVERIFIED。停止H4，等待审查。
