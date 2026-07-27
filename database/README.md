# database

## 名称
数据契约层：迁移、schema（含产消登记）、种子；逻辑分域 market_data / oltp / ref_data。

## 数据库引擎
**PostgreSQL（唯一支持）**。已弃用 SQLite 文件库。

| 模式 | 配置 | 说明 |
| --- | --- | --- |
| 本地嵌入式（默认） | 不设 `ASHARE_DATABASE_URL`，`pip install pgembed` | 数据目录 `data/pgdata`，库名 `ashare` |
| Docker | `docker compose up -d postgres` | 见根目录 `docker-compose.yml` |
| 外部实例 | `ASHARE_DATABASE_URL=postgresql+psycopg://user:pass@host:5432/ashare` | 生产推荐 |

迁移：
```bash
cd backend
python main.py migrate
```
迁移脚本为 PostgreSQL 方言（`BIGSERIAL` 等），版本记录在 `schema_migrations`。当前迁移至 **`031_strategy_sleeve.sql`**（新文件从 `032` 起）。

数据一致性速查（过账后）：
- `sum(sleeve)`（account+symbol）应对齐 `ledger_balance` POSITION
- `sum(lot)`（account+strategy_version+symbol）应对齐对应 sleeve
- 开发冒烟若见 `strategy_version=''` 与命名 sleeve 并存，属 031 回填+新仓叠加，见 `backend/ledger/README.md`

## 生产数据与落库表

| 生产数据 | 落库表 | 写入时机/说明 |
| --- | --- | --- |
| 不产生业务行数据 | — | 本目录定义/迁移表结构与种子；业务写入在 backend |
| 表契约说明 | （文档）`schema/` | 产消登记 |

## 本目录模块一览

| 模块/子目录 | 路径 | 主要作用 |
| --- | --- | --- |
| migrations | `migrations/` | 版本化 schema 变更（PostgreSQL） |
| schema | `schema/` | 可读契约 + **生产者/消费者登记** |
| seeds | `seeds/` | 开发/测试幂等种子 |

## 协作模块索引（供 AI Agent）

| 模块 | README | 主要作用 | 与本模块关系 |
| --- | --- | --- | --- |
| backend | `../backend/README.md` | 全部读写方 | 下游实现 |
| shared | `../backend/shared/README.md` | 连接池 / 迁移执行 | 运行时入口 |

## 边界
- 做：定义并版本化表；登记每张跨模块表的生产者/消费者/提交语义。
- 不做：业务计算；被 frontend 直连；用 seed 替代生产 ingest。

## 不变量
- 契约先于代码；跨模块表必须有稳定键与产消登记
- 物理可分库，逻辑契约仍在本目录
- 禁止再引入 SQLite 作为业务落库
