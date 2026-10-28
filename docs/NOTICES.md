# 来源与许可

Aevora 源码使用随包提供的 MIT LICENSE。依赖、数据库和浏览器组件保留
各自许可，公开分发不重新授权第三方代码。

- Cytoscape.js：图展示，许可原文位于 `console/third_party/CYTOSCAPE_LICENSE`，
  前端 bundle 保留 legal comments。
- esbuild：MIT，前端开发构建依赖。
- Playwright：Apache-2.0，维护者浏览器检查工具，不是产品运行依赖。
- FalkorDB server：独立下载的官方固定镜像，采用其上游 SSPL v1，不作为
  Aevora MIT 源码的一部分嵌入公开 source ZIP。
- Python、FalkorDB/Redis SDK、MCP SDK、Starlette、Uvicorn 和传递依赖使用
  各自安装元数据中的许可。版本由包元数据与 lockfile 决定。
- Go Runtime 的官方 MCP SDK、Cobra、go-winio、golang.org/x/sys、golang.org/x/net及传递依赖
  由 `go-runtime/go.mod` / `go.sum` 固定，保留各自上游许可。原生构建器逐目标
  使用google/go-licenses收集许可，并保留模块根的完整补充notice、Go与Cytoscape
  原文，打包到THIRD-PARTY-LICENSES.txt。构建清单不等于平台运行或正式发行验收。
- mvdan.cc/sh/v3：BSD-3-Clause；固定版本的syntax解析器用于保守分类检查命令，
  不使用其shell解释器。版本与校验和随Go依赖固定，许可纳入原生构建依赖归档。

Aevora 与其独立实验环境使用 OpenAI Codex 辅助开发。原生会话、工具活动、
维护者 seed、自然来源、外部观察和可信结果的权限分别记录；Agent 自述
不替代原始证据。公开回放只含有界投影，原始私有资料不随包分发。

Core/Console、图服务和模型 Runtime 各自承担既有能力，没有新增另一套
Agent 调度器或替代图引擎。部署环境、外部发布、竞赛资格和第三方法律
认证不由这些说明自动保证。
# 原生本地存储

Go产品依赖固定于`go-runtime/go.mod`和`go.sum`。SQLite驱动使用
[modernc.org/sqlite](https://pkg.go.dev/modernc.org/sqlite)（BSD-3-Clause）；
SQLite本体为[public domain](https://sqlite.org/copyright.html)。
传递依赖包括modernc.org/libc/mathutil/memory及其许可，发行归档需携带实际
构建依赖的许可正文；`ncruces/go-sqlite3`仅用于维护者外置选型实验，不进入产品依赖。
