# research_lab

## 名称
研究实验区：基线因子计算、落库与 IC/分层评估；产出默认不可直接实盘。

## 生产数据与落库表

| 生产数据 | 落库表 | 写入时机/说明 |
| --- | --- | --- |
| 因子值 | `research_factor_value` | `research` 计算任务 UPSERT（幂等） |
| 实验运行 | `research_run` | 计算/评估任务元数据 + `meta_json`（`report.ic_*` 供晋升 LIVE 质量门） |

迁移：`database/migrations/017_research_lab.sql`。

## 基线因子

| factor_code | 定义 | 数据源（点时） |
| --- | --- | --- |
| `MOM_20` | `adj_close_t / adj_close_{t-20} - 1` | `processed_equity_bar_1d` |
| `VAL_PE_PCT` | 当日 Universe 内 PE-TTM 截面分位；PE≤0→最差档 1.0 | `raw_valuation_1d.pe_ttm` |
| `FLOW_NET_5` | 近 5 日主力净流入之和 / 近 5 日成交额之和 | `raw_money_flow`（STOCK_FLOW）+ 日线 `amount` |
| `TECH_RSI_14` | 透传 `RSI_14` | `processed_tech_indicator_1d` |
| `TECH_MACD_HIST` | 透传 `MACD_HIST` | `processed_tech_indicator_1d` |
| `TECH_MA20_BIAS` | `adj_close / MA_20 - 1` | tech `MA_20` + processed 日线 |

技术指标因子依赖先跑：`data_process --kind tech_indicator`（日更 `daily` 已含 suite=core）。

## 协作模块索引（供 AI Agent）

| 模块 | README | 主要作用 | 与本模块关系 |
| --- | --- | --- | --- |
| data_process | `../data_process/README.md` | processed 行情 / tech 指标 | 上游（经库） |
| data_quality | `../data_quality/README.md` | dq_gate | 默认要求 passed |
| security_master | `../security_master/README.md` | Universe 快照 | 过滤标的 |
| alpha_fundamental / alpha_flow | `../data_ingest/...` | 估值/资金 raw | 上游（经库）；schedule 含 valuation+stock_flow |
| backtest | `../backtest/README.md` | 回测 | `FACTOR_TOP_N` 经库读本表；禁止互相 import |
| strategy_registry | `../strategy_registry/README.md` | 晋升 | LIVE 质量门读本表 IC 报告 |
| orchestrator | `../orchestrator/README.md` | 日更 | `factor_refresh` 调本模块重算 LIVE 因子 |
| signal_prod | `../signal_prod/README.md` | 生产信号 | 下游只读本表（经库） |

## 边界
- 做：因子纯函数计算、落库、IC/分层评估；写 `research_*`；消费已落库 tech 指标。
- 不做：通用因子框架；直接写生产信号；调用 execution；绕过 DQ（除非显式 `--no-dq-check`）；算技术指标本身（属 `data_process`）。

## 运行

```bash
cd backend
python main.py migrate
# 计算（短窗冒烟）
python main.py research --factor MOM_20 --universe TOP100 --start 2026-06-01 --end 2026-07-23
python main.py research --factor FLOW_NET_5 --universe TOP100 --start 2026-06-01 --end 2026-07-23
python main.py research --factor TECH_RSI_14 --universe TOP100 --start 2026-06-01 --end 2026-07-23
python main.py research --factor TECH_MA20_BIAS --universe TOP100 --start 2026-06-01 --end 2026-07-23
# 评估（需已有因子值；t 日因子对 t+1 ret_1d）
python main.py research --factor TECH_RSI_14 --evaluate --universe TOP100 --start 2026-06-01 --end 2026-07-23
python main.py backtest --strategy FACTOR_TOP_N --factor TECH_RSI_14 --universe TOP100 --start 2026-06-01 --end 2026-07-23
python -m research_lab.selfcheck
python -m pytest tests/test_research_factors.py -q
```

## 不变量
- 禁止未来函数：动量用历史 adj_close；评估严禁同日收益；tech 只读当日及以前已落库指标
- 默认 `dq_gate=passed` 才可研究消费
- 实验产出不得被 execution 直接消费
