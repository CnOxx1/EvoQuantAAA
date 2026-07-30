# research_lab

## 名称
研究实验区：基线因子计算、落库与 IC/分层评估；产出默认不可直接实盘。

## 生产数据与落库表

| 生产数据 | 落库表 | 写入时机/说明 |
| --- | --- | --- |
| 因子值 | `research_factor_value` | `research` 计算任务 UPSERT（幂等） |
| 实验运行 | `research_run` | 计算/评估/证据包元数据；`EVIDENCE_PACK` 含 OOS |
| 证据冻结 | `research_evidence_freeze` | `research --freeze` / `--freeze-run`；幂等按 artifact_hash |

迁移：`017_research_lab.sql`、`036_evidence_freeze.sql`。

## 基线因子 / 可注册模板

| factor_code（种子） | 模板 | 定义 |
| --- | --- | --- |
| `MOM_20` | `MOM` | `adj_close_t / adj_close_{t-N} - 1`（N=lookback） |
| `VAL_PE_PCT` | `VAL_PE_PCT` | 当日 Universe 内 PE-TTM 截面分位 |
| `FLOW_NET_5` | `FLOW_NET` | 近 N 日主力净流入 / 成交额 |
| `TECH_*` | `TECH_PASS` | 透传任意 `processed_tech_indicator_1d.indicator_code` |

迁移 `039`：`research_factor_def`；UI/gateway 可注册新码（如 `MOM_30`）并 `POST /v1/research/runs` 计算。

技术指标因子依赖先跑：`data_process --kind tech_indicator`（日更 `daily` 已含 suite=core）。

## 边界
- 做：模板化因子定义与计算、落库、IC/分层评估；写 `research_*`；消费已落库 tech 指标。
- 不做：任意公式 DSL；直接写生产信号；调用 execution；绕过 DQ（除非显式 `--no-dq-check`）；算技术指标本身（属 `data_process`）。

## 研究证据包与冻结

多因子 IC + soft 结论 + OOS（年切或 walk-forward）+ 硬 OOS 门槛；可选回测回写；可冻结为不可变产物（迁移 `036`）。

```bash
cd backend
# 年切证据包（短窗冒烟）
python main.py research --evidence --factor ALL --universe TOP100 \
  --start 2026-06-01 --end 2026-07-23
# walk-forward（开发机用小窗；长窗在有数据的环境跑，勿本机 bulk）
python main.py research --evidence --factor MOM_20 --universe TOP100 \
  --start 2026-06-01 --end 2026-07-23 \
  --split-mode walk_forward --wf-train-days 10 --wf-test-days 5 --wf-step-days 5
# 生成后冻结（硬门槛未过则拒绝；--force 须 --reason）
python main.py research --evidence --factor MOM_20 --universe TOP100 \
  --start 2026-06-01 --end 2026-07-23 --freeze
python main.py research --freeze-run re_xxx --reason "oos review"
python main.py research --list-freezes
python -m pytest tests/test_research_evidence.py -q
```

落库：
- `research_run.factor_code=EVIDENCE_PACK`，`meta_json.mode=evidence`（含 `split_mode` / `hard_oos` / `artifact_hash`）
- `research_evidence_freeze`：冻结快照 + `artifact_hash` 幂等

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
python main.py research --evidence --factor ALL --universe TOP100 --start 2026-06-01 --end 2026-07-23
python main.py backtest --strategy FACTOR_TOP_N --factor TECH_RSI_14 --universe TOP100 --start 2026-06-01 --end 2026-07-23
python -m research_lab.selfcheck
python -m pytest tests/test_research_factors.py tests/test_research_evidence.py -q
```

## 不变量
- 禁止未来函数：动量用历史 adj_close；评估严禁同日收益；tech 只读当日及以前已落库指标
- 默认 `dq_gate=passed` 才可研究消费
- 实验产出不得被 execution 直接消费
