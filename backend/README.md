# backend

## 名称
后端业务层：按交易真相拆分的模块；经库交接；由 orchestrator 调度；对外经 api_gateway。

## 生产数据与落库表

后端各子模块分别落库；本目录本身不写业务表。汇总见 `../database/schema/README.md`。

| 生产数据 | 落库表 | 写入时机/说明 |
| --- | --- | --- |
| （本目录无） | — | 落库由 `data_ingest/*`、`ledger` 等子模块完成 |


## 本目录模块一览

| 模块/子目录 | 路径 | 主要作用 |
| --- | --- | --- |
| shared | `shared/` | 无业务编排的共享工具与类型 |
| api_gateway | `api_gateway/` | 对外 BFF/API：鉴权、聚合、统一错误码 |
| orchestrator | `orchestrator/` | 任务 DAG/定时，只传引用 ID |
| security_master | `security_master/` | 证券主数据与 Universe 快照 |
| data_ingest | `data_ingest/` | 量化导向：CORE(ref+market) / ALPHA(基本面·资金·文本) |
| data_process | `data_process/` | 清洗复权对齐 → 加工表 |
| data_quality | `data_quality/` | DQ 门禁（未通过不得进信号） |
| research_lab | `research_lab/` | 实验因子/信号（不可直接实盘） |
| signal_prod | `signal_prod/` | 已晋升生产信号（带版本） |
| strategy_registry | `strategy_registry/` | 策略/因子版本与晋升状态 |
| backtest | `backtest/` | A 股约束回测与报告 |
| portfolio_construct | `portfolio_construct/` | 组合构建 → 目标持仓草稿 |
| risk_engine | `risk_engine/` | 硬风控、Kill Switch；可否决执行 |
| execution | `execution/` | OMS：委托/成交事件 |
| ledger | `ledger/` | 资金持仓账本过账（T+1） |
| ops_monitor | `ops_monitor/` | 监控、对账、告警、受控重跑 |

废弃：`research_factor/`、`portfolio_risk/`（勿创建、勿提交）。

## 协作模块索引（供 AI Agent）

| 模块 | README | 主要作用 | 与本模块关系 |
| --- | --- | --- | --- |
| database | `../database/README.md` | 契约与产消登记 | 上游契约 |
| frontend | `../frontend/README.md` | UI | 下游（经 api_gateway） |

## 边界
- 做：实现主链路各能力；模块独立可测；编排与对外入口集中。
- 不做：模块互相 import 内部实现；业务模块私自调度下游重逻辑；frontend 直连库；用 shared 做编排。

## 输入
- `database/` 已迁移表/视图
- 配置与密钥（仅 backend / 运维）
- 编排引用：`batch_id` / `job_id` / `run_id` / `strategy_version` / `portfolio_id`

## 输出
- 约定表中的业务数据与任务状态
- 经 api_gateway 暴露的 API
- orchestrator 发出的引用类事件

## 运行

```bash
cd backend
pip install -r requirements.txt
python main.py migrate

# 短窗冒烟
python main.py core_ref --p0 --start 2026-07-01 --end 2026-07-31 --source akshare
python main.py security_master --p0 --as-of 2026-07-23
python main.py core_market --p0 --start 2026-07-01 --end 2026-07-23 --symbol 600000 --symbol 000001

# 长窗推荐（TOP100，见根 README / data_ingest/README）
python main.py core_ref --kind calendar --start 2020-01-01 --end 2026-07-25
python main.py core_market --p0 --universe TOP100 --start 2023-01-01 --end 2026-07-23 \
  --skip-existing --min-bars 500 --chunk-size 8 --index 000300
python main.py data_process --p0 --universe TOP100 --universe-as-of 2026-07-23 \
  --start 2023-01-01 --end 2026-07-23 --factor-type qfq --index 000300
python main.py data_quality --scope CORE --universe TOP100 --start 2023-01-01 --end 2026-07-23 \
  --factor-type qfq --index 000300
python main.py backtest --universe TOP100 --start 2023-01-01 --end 2026-07-23 \
  --strategy EW_HOLD --factor-type qfq

# 停牌/涨跌停长窗、交易日增量、估值等见 data_ingest/README
python main.py core_market --kind suspend --start 2023-01-01 --end 2026-07-23 \
  --chunk-months 1 --skip-existing
python main.py daily --universe TOP100 --as-of 2026-07-23
```

- 总入口：`main.py`（子命令按模块扩展；含 `daily` 交易日增量）
- 环境：`research` / `paper` / `live`（待接线）
- 默认库：PostgreSQL（pgembed / `ASHARE_DATABASE_URL`）；已弃用 SQLite
- 行情 kinds / 接口映射：[`data_ingest/core_market/README.md`](./data_ingest/core_market/README.md)
- 共享写库/重试：[`shared/README.md`](./shared/README.md)（`bulk_upsert` / `akshare_call`）

## 不变量
- 跨模块只经已提交库数据交接
- DQ 未通过不得进 research_lab/signal_prod
- 实验信号不得绕过晋升进入 execution
- risk 未放行或 kill switch 开启时 execution 不得新开仓
- execution 不直接改账本余额，只产生事件由 ledger 过账
