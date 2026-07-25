# data_process

## 名称
数据处理：读已提交 `raw_*`，计算复权价/日收益/可成交掩码/基本面 PIT，写入 `processed_*`。

## 生产数据与落库表

| 生产数据 | 落库表 | 写入时机/说明 |
| --- | --- | --- |
| 加工批次元数据 | `process_batch` | create → committed/failed |
| 复权日线 + 掩码 | `processed_equity_bar_1d` | kind=`equity_1d` |
| 指数日线 + 收益 | `processed_index_bar_1d` | kind=`index_1d` |
| 基本面 PIT 区间 | `processed_fund_snapshot` | kind=`fundamental_pit`（迁移 `018`） |

## process_kind

| kind | 优先级 | 输入 | 输出要点 |
| --- | --- | --- | --- |
| `equity_1d` | P0 | 日线+复权+停牌+涨跌停板；缺板时**价格推导**回退 | `adj_*`、`ret_1d`、`can_buy`/`can_sell` |
| `index_1d` | P0 | `raw_index_bar_1d` | `ret_1d` |
| `fundamental_pit` | P1 | `raw_fund_statement` / `raw_fund_indicator` | 区间快照：`valid_from`/`valid_to`（`publish_date`=`announce_date`） |

## 计算口径

- 复权：`adj_price = raw_price * factor`，默认 `factor_type=qfq`。
- 收益：`ret_1d = adj_close_t / adj_close_{t-1} - 1`。
- 停牌 / 涨跌停板：`raw_suspend` / `raw_limit_board`。
- **涨跌停推导回退**（板缺失时）：未复权 close vs 前收；主板 ±10%、30/68 ±20%、ST ±5%（容差 0.2%）；`source` 标注 `limit_derived`。
- 基本面 PIT：按公告日构造可见区间；公告日前不可见；更正（更晚公告）覆盖旧区间。
- 多源：同一键优先 `preferred_source`。

## 边界
- 做：按区间/标的读 raw，写 processed；幂等可重跑。
- 不做：拉外部行情；替代 DQ；算因子/信号。

## 运行

```bash
cd backend
python main.py migrate
python main.py data_process --p0 --start 2026-07-01 --end 2026-07-23 --symbol 600000 --index 000300
python main.py data_process --kind fundamental_pit --symbol 600000
python -m data_process.selfcheck
```

## 不变量
- 只读已落库 raw；出模块必须落 `processed_*`
- `adj_factor` 缺失的日线行跳过并计数，不得静默用 1.0
- 基本面严禁用 `ingested_at` 当点时；只用 `announce_date`
