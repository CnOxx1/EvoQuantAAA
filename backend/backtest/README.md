# backtest

## 名称
回测引擎：读 `processed_*` + Universe + `dq_gate` + 统一 `cost_params`，做 A 股约束撮合并落库报告。

## 生产数据与落库表

| 生产数据 | 落库表 | 写入时机/说明 |
| --- | --- | --- |
| 费用参数 | `cost_params` | 迁移种子 `v1_ashare_default` |
| 回测运行 | `backtest_run` | 开始 running → committed/failed |
| 日净值 | `backtest_nav` | 每日 cash/市值/基准 |
| 成交假设 | `backtest_trade` | 建仓/调仓成交 |

## 策略

| strategy_code | 行为 |
| --- | --- |
| `EW_HOLD` | 首个可买日等权建仓并持有（未成交目标顺延至对齐） |
| `EW_REBALANCE` | 等权 + `--rebalance-days N` 定期再平衡 |
| `FACTOR_TOP_N` | 读 `research_factor_value`；调仓日用**前一交易日**因子 top N 等权 |

底层通用撮合：`engine.run_target_weights`（目标权重 → 先卖后买）。

## A 股约束（引擎强制）

- **T+1**：按买入**批次 FIFO**（加仓新建 lot，不合并最早 `buy_date`）；`buy_date < 当日` 才可卖
- **can_buy / can_sell**：涨停不可买、跌停/停牌不可卖；受阻订单顺延
- **整手**：`lot_size`（默认 100）向下取整
- **定价**：成交与市值优先**未复权 `close`**（缺则 `adj_close`），与 live 对齐
- **费用**：买入佣金；卖出佣金 + **印花税**；滑点计入成交价
- **pending**：调仓日写入目标；对齐后清空，避免非调仓日微扰
- 现金不足按比例缩量买入，不允许透支

## 约束
- 默认要求 `dq_gate(CORE, start, end, factor_type)=passed`
- 只交易有 `processed_equity_bar_1d` 的标的（Universe 其余跳过并记 coverage）
- 费用与 `execution` 共用 `cost_params` 版本

## 边界
- 做：模拟成交、写报告；绑定 Universe/DQ/cost 版本。
- 不做：实盘下单；接受未落库信号 DF；模块内写死与 live 不一致的费率。

## 运行

```bash
cd backend
python main.py migrate
python main.py backtest --strategy EW_HOLD --start 2026-07-01 --end 2026-07-23 --symbol 600000 --symbol 000001
python main.py backtest --strategy EW_REBALANCE --rebalance-days 20 --universe TOP100 --start 2026-06-01 --end 2026-07-23 --factor-type qfq
# 因子 → 回测（须先 research 落库）
python main.py research --factor MOM_20 --universe TOP100 --start 2026-06-01 --end 2026-07-23
python main.py backtest --strategy FACTOR_TOP_N --factor MOM_20 --top-n 20 --rebalance-days 20 --universe TOP100 --start 2026-06-01 --end 2026-07-23
python -m backtest.selfcheck
python -m pytest tests/test_backtest_engine.py -q
```

## 不变量
- T+1 / 涨跌停 / 停牌 / 整手 / 印花税（卖）默认开启
- 未过 DQ 不得宣称区间可回测（除非显式 `--no-dq-check` 调试）
