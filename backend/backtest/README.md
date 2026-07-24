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

## 策略（P0）

| strategy_code | 行为 |
| --- | --- |
| `EW_HOLD` | 首个可买日等权建仓并持有；整手 100；佣金/印花税/滑点读 cost |

## 约束
- 默认要求 `dq_gate(CORE, start, end, factor_type)=passed`
- 只交易有 `processed_equity_bar_1d` 的标的（Universe 其余跳过并记 coverage）
- `can_buy=0` 不得买入；费用与 `execution` 共用 `cost_params` 版本

## 边界
- 做：模拟成交、写报告；绑定 Universe/DQ/cost 版本。
- 不做：实盘下单；接受未落库信号 DF；模块内写死与 live 不一致的费率。

## 运行

```bash
cd backend
python main.py migrate
python main.py backtest --strategy EW_HOLD --start 2026-07-01 --end 2026-07-23 --symbol 600000 --symbol 000001
python main.py backtest --strategy EW_HOLD --start 2026-07-01 --end 2026-07-23 --universe HS300
python -m backtest.selfcheck
```

## 不变量
- T+1 / 涨跌停 / 停牌 / 整手 / 费用默认开启（P0 持有策略主要体现买入约束与费用）
- 未过 DQ 不得宣称区间可回测（除非显式 `--no-dq-check` 调试）
