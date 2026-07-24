# shared

## 名称
后端跨模块共享工具与类型（无业务编排）。

## 生产数据与落库表

| 生产数据 | 落库表 | 写入时机/说明 |
| --- | --- | --- |
| 无业务数据 | — | 仅提供 DB 连接/工具；不拥有业务表写入职责 |


## 本目录模块一览
无子模块；本目录即共享库实现。

## 协作模块索引（供 AI Agent）

| 模块 | README | 主要作用 | 与本模块关系 |
| --- | --- | --- | --- |
| backend（父） | `../README.md` | 模块总览 | 父目录 |
| database | `../../database/README.md` | 契约 | 类型可对齐契约 |
| 各业务模块 | `../README.md` | 消费者 | 可引用本库；本库不得反依赖 |

## 数据库
- 引擎：**PostgreSQL**（SQLAlchemy + psycopg）
- 默认：嵌入式 `pgembed` → `data/pgdata`，库 `ashare`
- 覆盖：`ASHARE_DATABASE_URL=postgresql+psycopg://...`
- 仓库代码仍可用 `?` 占位符，由 `shared.db` 转换为绑定参数

## 边界
- 做：日志、配置读取、DB 连接辅助、ID 工具、通用错误类型。
- 不做：依赖任何业务模块；实现 DAG 调度；隐藏跨模块传 DataFrame。

## 输入
- 无业务上游

## 输出
- 稳定、版本敏感的工具 API

## 运行
- 被业务模块引用；无独立长驻进程

## 不变量
- 不得 import `backend` 下其他业务模块
- 不得成为「第二个 orchestrator」
