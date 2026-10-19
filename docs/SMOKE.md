# SMOKE-001

Smoke 与正式 Episode A–D 分离，验证取消订单后的库存恢复与幂等性。

正确基线：初始 10 → 创建/预留 3 后 7 → 取消后 10 → 再次取消仍为 10。缺陷基线：最后一步增加到 13。缺陷生成器只用于 Smoke：重复释放逻辑与缺少库存守恒约束共同允许错误落库；正确参考补丁同时恢复业务幂等保护与数据库约束。

## 开发者双重验证

```bash
scripts/orderflow evaluate --episode SMOKE-001
# FAIL，退出 1
scripts/orderflow evaluate --episode SMOKE-001 --submission evaluator/reference_patches/SMOKE-001.diff
# PASS，退出 0
scripts/orderflow evaluate --episode SMOKE-001 --submission app
# 正确工作区提交，PASS，退出 0
scripts/orderflow reset --episode SMOKE-001
scripts/orderflow evaluate --episode SMOKE-001
# 新 Run，缺陷仍 FAIL
```

参考补丁属于宿主维护者验收材料，不提供给被测 Agent。工作区路径只接收 `app/*.py`；对应 app 目录不允许符号链接。补丁会应用到新的缺陷基线，使用真实 `git apply --check` 与 `git apply`。语法错误保留为评测 ERROR，不会由主进程导入候选代码。

## 独立测试

隐藏套件在宿主运行 8 项测试，使用通用 RPC 操作隔离业务实例：库存恢复及重复取消、多订单对账、无预留取消、重复创建/预留、库存不足回滚、初始化/重置、进程重启持久性、非法请求回滚。每项测试使用独立数据库；数据库实际写入 SQLite。Phase 2 保留这些测试，并在业务 audit() 断言后关闭 Worker、增加宿主只读数据库 Oracle 检查。suite ID 为 `smoke`，版本 `2.0.0`；Scenario 与 Fixture 仍为 `1.0.0`。

公开测试仅覆盖正常单次取消，用于确保缺陷基线基础业务可运行。Agent 可以在隔离 shell 中执行：

```bash
scripts/orderflow prepare --episode SMOKE-001
scripts/orderflow shell --run-id <id> -- /usr/bin/python3.12 -m unittest discover -s tests/public
```

隐藏断言、测试名称、路径、参考代码与宿主报告不挂载到工作进程。业务 RPC 是普通调用数据；不是隐藏源码注入。报告位于宿主，运行后由维护者按实验权限提供。

## 判分与归档

PASS 要求真实 pytest 退出 0、JUnit 解析成功、准确收集 8 项且逐项身份与必要测试集合相符、无失败、无 ERROR、无 skip。pytest 退出 1 且断言失败为 FAIL。缺失 XML、计数/身份不符、重复或空测试、skip、启动失败及结果冲突为 ERROR；超时强制结束测试与其子进程组，结果 TIMEOUT。Episode A 使用独立的 `episode_a` suite 与 fixture；B/C/D 返回 NOT_IMPLEMENTED，不调用 Smoke 或 A oracle。

`runs/<uuid>/evaluation_report.json` 含总体状态、逐项测试、场景/变体、真实提交、Evaluator/Fixture/Suite/Private Manifest 摘要和运行环境指纹、UTC 时间、异常、Artifact 路径。宿主 SQLite 检查保存为 `oracle-*.json`，并汇总进报告。`execution_trace.jsonl` 记录 Runner 生命周期及手动接收；没有采集 Codex 内部任务委派、token 或经验调用。

自动/显式重置清理评测临时数据库，重新生成公开初始数据库，保留提交快照、补丁、JUnit 和执行日志。重复运行验证比较状态及逐项 outcome，不要求 UUID、时间与测试耗时相同。

## 一键验收

```bash
scripts/python312 scripts/validate_phase1.py
```

脚本实际安装/检查依赖、执行开发者测试、业务闭环、公开沙箱命令、正确/缺陷 Smoke 提交重复评测、错误/超时提交、Episode 状态检查、报告查询及重置。Phase 2 将 A 的状态期望更新为已实现；B/C/D 的未实现检查保留。每条命令的 stdout/stderr、退出状态和时间写入唯一验收目录，并在该新验收目录生成 `PHASE1_VALIDATION_REPORT.md`；原报告已迁入 [历史记录](history/phase1-3/PHASE1_VALIDATION_REPORT.md)。Episode A 的正式并发与 10 轮重复性验收归入 Phase 2 报告。
