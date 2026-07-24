# data_quality

## 名称
数据质量门禁：对 `processed_*` 跑 CORE 规则，写入 `dq_result`，并更新区间闸门 `dq_gate`。  
**error 规则失败 → gate=failed，研究/回测不得宣称该区间可用。**

## 生产数据与落库表

| 生产数据 | 落库表 | 写入时机/说明 |
| --- | --- | --- |
| DQ 运行 | `dq_run` | 每次检查一条 |
| 规则结果 | `dq_result` | `(dq_run_id, rule_code)` 幂等 |
| 区间闸门 | `dq_gate` | `(scope, start, end, factor_type)` 最新状态 |

## CORE 规则（P0）

| rule_code | severity | 含义 |
| --- | --- | --- |
| `equity_nonempty` | error | processed 股票日线非空且标的齐全 |
| `index_nonempty` | error | processed 指数日线非空 |
| `adj_complete` | error | `adj_close`/`adj_factor` 齐全 |
| `price_positive` | error | close/adj_close > 0 |
| `ret_coverage` | error | 除首日外 `ret_1d` 非空 |
| `mask_consistency` | error | 停牌/涨跌停与 can_buy/can_sell 一致 |
| `ohlc_order` | warn | low/high 与 open/close 关系 |
| `extreme_return` | warn | \|ret_1d\| > 22% |
| `calendar_align` | warn | 交易日 ⊆ 开市日历（无日历则跳过） |

闸门判定：任一 **error** fail → `failed`；warn 不影响 pass。

## 边界
- 做：读 processed（及必要日历），写 DQ 结果与 gate。
- 不做：改行情修数冒充通过；拉外部源；算因子。

## 运行

```bash
cd backend
python main.py migrate
python main.py data_process --p0 --start 2026-07-01 --end 2026-07-23 --symbol 600000 --symbol 000001
python main.py data_quality --scope CORE --start 2026-07-01 --end 2026-07-23 --symbol 600000 --symbol 000001
python -m data_quality.selfcheck
```

## 协作模块

| 模块 | 关系 |
| --- | --- |
| data_process | 上游 processed |
| research_lab / backtest / signal_prod | 须 `dq_gate.status=passed` |
| ops_monitor | 可消费 fail 告警 |

## 不变量
- fail 批次/区间禁止被 signal_prod 与未豁免 research 生产路径消费
- 结果可审计、可重跑；不静默改数
