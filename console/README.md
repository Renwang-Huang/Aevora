# Aevora Console

Core 的只读展示界面，包含 Activity & Decisions、Experience Explorer 和
Governance Timeline。界面显示公共投影，不审批候选或创建可信 Outcome。
默认 LIVE 展示当前项目与 Run；连接、空图、待处理候选和可用经验分别显示。
默认界面使用中文，保留 LIVE、Run、Query、APPLY 等技术标识。首屏解释页面用途、
项目进度、四项指标和下一步；“第一次使用”包含操作流程、术语和可复制的 Agent 提示。
筛选、运行标识与原始证据可展开查看。查询返回零经验时直接解释原因和后续操作，
缺失数量保持未知。自动刷新可暂停，后台读取保留已展开的说明，读取失败清除旧数据。
Case A/B/C 通过明确的 Demo replay 入口访问。普通 LIVE 启动不需要演示目录。
LIVE 默认 17805，Demo 默认 17804；CLI 自动加载 Host profile 并跟随当前 MCP 会话。

从仓库根安装 `aevora_core` 和 `console`，用根 README 命令启动公共回放。
自己的图与 MCP 通道按[快速开始](../docs/QUICKSTART.md)配置；页面和 API
见[Console 指南](../docs/CONSOLE.md)。

前端开发使用 package.json / lockfile 中固定的 Node/npm：

```sh
npm --prefix console ci --ignore-scripts
npm --prefix console run build
```

LIVE 按数据库游标分页读取 Run、查询、候选和经验；图只读取页面或所选经验的
有限邻域。项目累计容量不再触发整图拒绝，单请求仍保留资源预算；未完整验证的
总数显示 UNKNOWN。页面大小、翻页和游标链接见 Console 指南。

构建产物进入 Python 包 static 资源。LIVE 读取实际 Core；REPLAY 校验独立
pin，二者不静默切换。图布局只表示展示关系，读取范围、缺失身份和结果
权限明确披露。许可见[来源与许可](../docs/NOTICES.md)。
