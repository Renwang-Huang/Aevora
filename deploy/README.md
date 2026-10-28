# 本地图服务与容器部署

按[快速开始](../docs/QUICKSTART.md)安装 Core/Console，选择自己的 Compose
project、loopback 端口与 graph。秘密目录在源码外，目录 0700、文件 0600。

compose.yaml 固定真实 FalkorDB image/digest，显式加载秘密配置，以 RDB
保存到所属 volume。使用 `docker compose -p <owned-project> ...` 区分实例，
停止时保留 volume。未完成 SAVE 的 crash tail 不保证零丢失。

公开应用 Docker context 应由维护者发布工具的显式 source allowlist 生成，
不直接把整个维护者仓库作为 context。数据库服务使用独立镜像和许可。
在导出的公开 source 根目录构建应用镜像：

```sh
docker build -f deploy/Dockerfile -t aevora-local .
```

`compose.yaml` 管理图服务，`Dockerfile` 构建 Core/Console 应用；镜像内公共
回放位于 `/opt/aevora/demo`。应用以 UID 1000 运行，默认只读服务绑定 loopback。
本地部署不构成多租户、敌对内核或外部托管认证。
