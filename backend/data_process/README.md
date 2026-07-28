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
| 日线技术指标 | `processed_tech_indicator_1d` | kind=`tech_indicator`（迁移 `020`） |

## process_kind

| kind | 优先级 | 输入 | 输出要点 |
| --- | --- | --- | --- |
| `equity_1d` | P0 | 日线+复权+停牌+涨跌停板；缺板时**价格推导**回退 | `adj_*`、`ret_1d`、`can_buy`/`can_sell` |
| `index_1d` | P0 | `raw_index_bar_1d` | `ret_1d` |
| `fundamental_pit` | P1 | `raw_fund_statement` / `raw_fund_indicator` | 区间快照：`valid_from`/`valid_to`（`publish_date`=`announce_date`） |
| `tech_indicator` | P1 | processed 日线或分钟（`--freq`） | 指标长表（1d / min） |
| `equity_15m` / `equity_60m` | P2 | `raw_equity_bar_min` + 当日 `raw_adj_factor` | `processed_equity_bar_min` 复权 OHLCV |

## 计算口径

- 复权：`adj_price = raw_price * factor`，默认 `factor_type=qfq`。
- 收益：`ret_1d = adj_close_t / adj_close_{t-1} - 1`。
- 停牌 / 涨跌停板：`raw_suspend` / `raw_limit_board`。
- **涨跌停推导回退**（板缺失时）：未复权 close vs 前收；主板 ±10%、30/68 ±20%、ST ±5%（容差 0.2%）；`source` 标注 `limit_derived`。
- 基本面 PIT：按公告日构造可见区间；公告日前不可见；更正（更晚公告）覆盖旧区间。
- 多源：同一键优先 `preferred_source`。
- **技术指标**（仍属本模块，不进 ingest）：
  - `suite=core`（日更默认）：`MA_*` / `EMA_*` / `MACD_*` / `RSI_14` / `BOLL_*`（13 码，`category=core`）
  - `suite=full`：pandas-ta **全部分类**（candle/cycle/momentum/overlap/performance/statistics/trend/volatility/volume；~150 函数 → ~250+ 序列）；`category` 写入长表
  - 输入复权 OHLCV；不拉外部；缺 bar 跳过；`--category` 可只跑某一类；日更只跑 core，避免全市场×全指标爆库
  - 与 `research_lab` 分工：指标=价量特征落库；研究侧经库消费为 `TECH_RSI_14` / `TECH_MACD_HIST` / `TECH_MA20_BIAS`
  - UI 经 `api_gateway`：`GET /v1/market/indicators` / `indicators/meta`（见 `backend/api_gateway/README.md`）

## 边界
- 做：按区间/标的读 raw（或已 processed 日线），写 processed；幂等可重跑。
- 不做：拉外部行情；替代 DQ；算研究因子/信号（见 `research_lab`）。
- 消费者：`research_lab` / `backtest` / **`api_gateway`（市场情报前端）**。

## 运行

```bash
cd backend
python main.py migrate
python main.py data_process --p0 --start 2026-07-01 --end 2026-07-23 --symbol 600000 --index 000300
python main.py data_process --kind fundamental_pit --symbol 600000
# 日线技术指标
python main.py data_process --list-tech-catalog
python main.py data_process --kind tech_indicator --universe TOP100 --start 2026-06-01 --end 2026-07-23
# 全量分类（短窗 / 少标的；本机勿 ALL_LISTED）
python main.py data_process --kind tech_indicator --suite full --symbol 600000 --start 2026-06-01 --end 2026-07-23 --force
python main.py data_process --kind tech_indicator --suite full --category momentum --symbol 600000 --start 2026-06-01 --end 2026-07-23 --force
# 分钟指标（须先有 raw+processed 分钟）
python main.py data_process --kind equity_15m --symbol 600000 --start 2026-07-21 --end 2026-07-23
python main.py data_process --kind tech_indicator --freq 15m --suite core --symbol 600000 --start 2026-07-21 --end 2026-07-23 --force
python -m data_process.selfcheck
python -m pytest tests/test_tech_indicator.py tests/test_tech_catalog.py tests/test_min_bars.py -q
```

## 不变量
- 只读已落库数据；出模块必须落 `processed_*`；`tech_indicator` **禁止**调 ingest/akshare
- `adj_factor` 缺失的日线行跳过并计数，不得静默用 1.0
- 基本面严禁用 `ingested_at` 当点时；只用 `announce_date`
