# 体验与演示

演示使用公共回放，具有独立的合同 pin 和实际来源。它展示已有记录，
不发起新的模型请求，不构成新任务成绩或因果收益证明。
Console 默认进入当前项目 LIVE；演示配置启动后，选择 “Demo replay” 或
打开 `http://127.0.0.1:17804/?mode=REPLAY`，再选择 Case A/B/C。

## 校验回放

```sh
python3 -I demo/verify_hero.py demo --sha256 c460d927331db3e2b262c848337afd3bb5b93007538941c546827b895bd86776
```

校验器检查来源身份、关系、生命周期与结果语义；不只比较非空摘要。
pin 必须来自独立可信交付来源，不能以不可信下载本身的哈希替代。
实际公开 source IDs 和 proof 在回放合同与 Console 中显示。

只读命令行 walkthrough 使用同一份回放：

```sh
python3 demo/walkthrough.py --sha256 c460d927331db3e2b262c848337afd3bb5b93007538941c546827b895bd86776
```

## 建议浏览顺序

1. **Activity / Case A**：查看真实候选的提议、来源核验、Host review、发布
   和另一次会话的读取。原始完成与 NO_PATCH 状态分别保留。
2. **Explorer / Case B**：比较 threads、workers、unknown 条件，观察实际
   前提对 APPLY、ABSTAIN、VERIFY 的影响。新空图使用 Replay 展示已有例子。
3. **Timeline / Case C**：切换 before、after、restored，查看一次实际受控
   证据边干预如何改变相关支持，旧 QuerySnapshot 保持原样。

三个 case 来源不同，不是一条连续 Agent 血缘。受控干预不冒充新 Agent
反馈，公开项目自测不提升为 VerifiedOutcome。采纳与因果收益保持未知。

## 录制或分享

保留画面中的模式、来源、时间和 pin；LIVE 只展示真实当前读取。出现
数据库/模型错误时保留实际状态，手动切 Replay 时明确说明。不要展示
秘密、grant、原始私有载荷或个人浏览器资料。视图与公共 API 的限制见
[Console](CONSOLE.md)；许可和辅助开发来源见[NOTICES](NOTICES.md)。
