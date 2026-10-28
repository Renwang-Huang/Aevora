# 本地工作流、备份与升级

## 日常任务

推荐使用快速开始中的自动连接。需要显式隔离一次任务时：

```sh
aevora task run --project my-project --name fix-build --client codex --enable-proposals
```

它启动官方客户端并为本次任务提供连接。退出后撤销所属通道，保留任务与历史。
任务成功退出不等于工程结果经过独立核验。
通过 `aevora task list --project my-project` 查看任务；固定任务可用 task resume 恢复。
版本、分支或工作区事实变化时需要新任务，旧查询与决策不被改写。

## 停止与查看

```sh
aevora status --project my-project
aevora host stop --project my-project
aevora host start --project my-project --background
```

停止或移除所属服务不删除数据库。后台模式不会默认登录自启；需要时显式使用 `--autostart`。

## 备份与恢复

```sh
aevora backup --project my-project --output /absolute/private/backup.db
aevora --config /absolute/private/restored/host.json restore --input /absolute/private/backup.db --sha256 BACKUP_SHA256 --data-dir /absolute/private/restored/data
```

备份使用 SQLite 一致性快照。记录命令返回的 SHA256；恢复要求新配置与新数据目录，
不会覆盖现有项目。不要用活动数据库文件的普通复制代替一致性备份。
配置、授权文件和数据库都属于你的私有状态，不应上传到公共仓库。

## 升级

从可信发行页下载新包并核对归档校验值。解压后，计算二进制自身的校验值：

```sh
sha256sum /absolute/new/aevora
aevora upgrade --project my-project --binary /absolute/new/aevora --sha256 BINARY_SHA256
```

归档校验值与二进制校验值不同。升级保留旧程序与一致性备份，检查平台和存储兼容性，
替换后恢复所属 Host；业务请求不会自动重放。升级现有运行实例后重新打开客户端会话。
首次使用新程序操作旧安装，可加 `--target /absolute/installed/aevora` 指定目标。

失败时保留升级回执，依据实际恢复状态处理；不手工覆盖数据库来掩盖失败。
schema不兼容时拒绝降级，卸载程序不会自动清除数据。
