# shared

## 名称
后端跨模块共享工具与类型（无业务编排）。

## 生产数据与落库表

| 生产数据 | 落库表 | 写入时机/说明 |
| --- | --- | --- |
| 无业务数据 | — | 仅提供 DB 连接/工具；不拥有业务表写入职责 |


## 本目录模块一览

| 文件 | 作用 |
| --- | --- |
| `db.py` | SQLAlchemy 连接；`?` → 命名绑定；`executemany` |
| `config.py` / `pg_local.py` | 配置与本地 pgembed |
| `logging_utils.py` | 日志 |
| `universe_resolve.py` | 从已提交 Universe 快照解析标的（只读库） |
| `ingest_batching.py` | `chunk_symbols` / `chunk_date_ranges` / `missing_date_ranges` / Universe 参数解析 |
| `bulk_upsert.py` | 通用分块 UPSERT（大包 executemany，小包 EXISTS 统计） |
| `akshare_call.py` | Akshare/HTTP 统一重试、退避、失败降噪 |
| `timeutil.py` | UTC ISO / `normalize_publish_time`（原 announcement 内工具上收） |

## 协作模块索引（供 AI Agent）

| 模块 | README | 主要作用 | 与本模块关系 |
| --- | --- | --- | --- |
| backend（父） | `../README.md` | 模块总览 | 父目录 |
| database | `../../database/README.md` | 契约 | 类型可对齐契约 |
| data_ingest | `../data_ingest/README.md` | 主要消费者 | 可引用；本库不得反依赖 |

## 数据库
- 引擎：**PostgreSQL**（SQLAlchemy + psycopg）
- 默认：嵌入式 `pgembed` → `data/pgdata`，库 `ashare`
- 覆盖：`ASHARE_DATABASE_URL=postgresql+psycopg://...`
- 仓库代码仍可用 `?` 占位符，由 `shared.db` 转换为绑定参数；批量写用 `ConnectionProxy.executemany`

## 边界
- 做：日志、配置、DB 辅助、Universe 解析、ingest 分块/批量写入、HTTP 重试。
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
