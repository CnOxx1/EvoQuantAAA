# data_process

## 名称
数据处理：读已提交 CORE `raw_*`，计算复权价/日收益/可成交掩码，写入 `processed_*`。

## 生产数据与落库表

| 生产数据 | 落库表 | 写入时机/说明 |
| --- | --- | --- |
| 加工批次元数据 | `process_batch` | create → committed/failed |
| 复权日线 + 掩码 | `processed_equity_bar_1d` | kind=`equity_1d` |
| 指数日线 + 收益 | `processed_index_bar_1d` | kind=`index_1d` |

## process_kind

| kind | 优先级 | 输入 | 输出要点 |
| --- | --- | --- | --- |
| `equity_1d` | P0 | `raw_equity_bar_1d` + `raw_adj_factor` + `raw_suspend` + `raw_limit_board` | `adj_*`、`ret_1d`、`can_buy`/`can_sell` |
| `index_1d` | P0 | `raw_index_bar_1d` | `ret_1d`（指数本身不复权） |

## 计算口径

- 复权：`adj_price = raw_price * factor`，默认 `factor_type=qfq`（与 ingest `adj_factor` 一致）。
- 收益：`ret_1d = adj_close_t / adj_close_{t-1} - 1`（按标的排序；首日为空）。
- 停牌：`raw_suspend` 有记录 → `is_suspended=1`。
- 涨跌停：`event_type` UP/DOWN → `is_limit_up` / `is_limit_down`。
- 可成交：`can_buy = !(suspend|limit_up)`；`can_sell = !(suspend|limit_down)`。
- 多源：同一键优先 `preferred_source`（默认 `akshare`）。

## 边界
- 做：按区间/标的读 raw，写 processed；幂等可重跑。
- 不做：拉外部行情；替代 DQ 放行；算因子/信号；接上游内存 DF。

## 运行

```bash
cd backend
python main.py migrate
# 短窗
python main.py data_process --p0 --start 2026-07-01 --end 2026-07-23 --symbol 600000 --symbol 000001 --index 000300
# 长窗（Universe 点时建议用快照 as_of，勿用区间起点）
python main.py data_process --p0 --universe TOP100 --universe-as-of 2026-07-23 \
  --start 2023-01-01 --end 2026-07-23 --factor-type qfq --index 000300
python -m data_process.selfcheck
```

## 协作模块

| 模块 | 关系 |
| --- | --- |
| data_ingest/core_market | 上游 raw |
| data_quality | 下游门禁（`python main.py data_quality --scope CORE ...`） |
| backtest / research_lab | 经 DQ 后消费 processed |

## 不变量
- 只读已落库 raw；出模块必须落 `processed_*`
- `adj_factor` 缺失的日线行跳过并计数，不得静默用 1.0 冒充
- 未 commit 的 `process_batch` 不得宣称区间可回测
