# core_market

## 名称
量化 CORE · 市场数据心脏：未复权行情 + 复权因子 + 停牌/涨跌停 + 指数基准（同域强制齐套）。

## 生产数据与落库表

| 生产数据 | 落库表 | 写入时机/说明 |
| --- | --- | --- |
| 股票日线 | `raw_equity_bar_1d` | kind=`equity_1d` |
| 复权因子 | `raw_adj_factor` | kind=`adj_factor`（`qfq`/`hfq`） |
| 停牌 | `raw_suspend` | kind=`suspend` |
| 涨跌停池 | `raw_limit_board` | kind=`limit`（长窗 `UP`/`DOWN`；短窗另含扩展池） |
| 指数日线 | `raw_index_bar_1d` | kind=`index_1d` |
| 公司行为 | `raw_corp_action` | kind=`corp_action`（P1） |
| 市场排名 | `raw_market_rank_1d` | kind=`market_rank`（P1） |
| 盘口异动 | `raw_abnormal_move` | kind=`abnormal_move`（P1） |
| 板块日线 | `raw_board_bar_1d` | kind=`board_1d`（P1） |
| 批次 | `ingest_batch` | 经 ingest_common |

迁移脚本：`003_core_market.sql`、`011_market_rank.sql`、`012_market_microstructure.sql`、`013_ingest_enhancements.sql`。

## 本目录模块一览
无子模块；按 `ingest_kind` 拉数。**策略侧不得在缺少 adj/suspend/limit 时单独宣称 equity_1d 可用。**  
默认灌数宇宙：`TOP100` / `SECTOR_LEADERS`（勿对 `ALL_LISTED` bulk）。

| ingest_kind | 优先级 | 输出表 | 量化用途 |
| --- | --- | --- | --- |
| `equity_1d` | P0 | `raw_equity_bar_1d` | 价量（未复权） |
| `adj_factor` | P0 | `raw_adj_factor` | 除权后收益 |
| `suspend` | P0 | `raw_suspend` | 停牌不可成交 |
| `limit` | P0 | `raw_limit_board` | 涨跌停约束（及短窗扩展池） |
| `index_1d` | P0 | `raw_index_bar_1d` | 基准/相对收益 |
| `corp_action` | P1 | `raw_corp_action` | 复权校验、事件 |
| `market_rank` | P1 | `raw_market_rank_1d` | 涨跌幅/量额/换手/人气榜 |
| `abnormal_move` | P1 | `raw_abnormal_move` | 盘口异动（火箭发射/大笔买卖等） |
| `board_1d` | P1 | `raw_board_bar_1d` | 行业/概念板块日线（轮动） |
| `equity_15m` | P2 | `raw_equity_bar_min` (freq=15m) | 15 分钟 K；东财 hist_min_em，回退新浪 minute |
| `equity_60m` | P2 | `raw_equity_bar_min` (freq=60m) | 60 分钟 K；同上 |

### 分钟 K 说明（15m / 60m）

- **链路**：`core_market equity_15m|60m` → `data_process equity_15m|60m`（当日 `adj_factor` 复权）→ 可选 `tech_indicator --freq 15m|60m`
- **源限制**：公开接口通常只给**近若干交易日**分钟窗；本机只做短窗少标的，禁止 ALL_LISTED 长回填
- **不进日更 schedule 默认路径**（避免拉爆）；按需 CLI

## 协作模块索引（供 AI Agent）

| 模块 | README | 主要作用 | 与本模块关系 |
| --- | --- | --- | --- |
| data_ingest（父） | `../README.md` | 总览 | 父目录 |
| ingest_common | `../ingest_common/README.md` | batch | 可引用 |
| core_ref | `../core_ref/README.md` | 日历/证券 | 同级上游 |
| data_process | `../../data_process/README.md` | 复权价、可成交掩码 | 主下游 |
| data_quality | `../../data_quality/README.md` | CORE 门禁 | 下游 |
| backtest | `../../backtest/README.md` | 撮合 | 间接（经 process） |

## 边界
- 做：上述 raw 的拉取与落库；因子口径写入 `factor_type`。
- 不做：计算复权 OHLCV/收益率；Universe；NLP；基本面。

## 输入
标的池、指数池、区间、源；`job_id` + kind

## 输出
对应 `raw_*` + `batch_id`

## 运行

```bash
cd backend
pip install -r requirements.txt
python main.py migrate

# 短窗冒烟
python main.py core_market --p0 --start 2026-07-21 --end 2026-07-23 --symbol 600000 --symbol 000001 --index 000300

# 分钟 K（短窗；建议先 mock 自检，再 akshare）
python main.py core_market --kind equity_15m --source mock --symbol 600000 --start 2026-07-21 --end 2026-07-23
python main.py core_market --kind equity_60m --symbol 600000 --start 2026-07-21 --end 2026-07-23
python main.py data_process --kind equity_15m --symbol 600000 --start 2026-07-21 --end 2026-07-23
python main.py data_process --kind tech_indicator --freq 15m --suite core --symbol 600000 --start 2026-07-21 --end 2026-07-23 --force

# 长窗推荐：TOP100 日线+复权（--min-bars 避免「已有少量日线就跳过」）
python main.py core_market --p0 --universe TOP100 --start 2023-01-01 --end 2026-07-23 \
  --skip-existing --min-bars 500 --chunk-size 8 --index 000300
python main.py core_market --kind index_1d --start 2023-01-01 --end 2026-07-23 \
  --index 000300 --index 000905 --index 000852

# 停牌 / 涨跌停：内建按月分块（替代临时脚本）
python main.py core_market --kind suspend --start 2023-01-01 --end 2026-07-23 \
  --chunk-months 1 --skip-existing
python main.py core_market --kind limit --start 2023-01-01 --end 2026-07-23 \
  --chunk-months 1 --skip-existing
# 短窗可一次拉齐（含强势/炸板等扩展池）
python main.py core_market --kind limit --start 2026-07-21 --end 2026-07-23

# 排名 / 异动 / 板块
python main.py core_market --kind market_rank --start 2026-07-01 --end 2026-07-23 --top-n 200
python main.py core_market --kind market_rank --start 2026-07-23 --end 2026-07-23 --top-n 200 --prefer-spot
python main.py core_market --kind abnormal_move --start 2026-07-23 --end 2026-07-23
python main.py core_market --kind board_1d --start 2026-07-01 --end 2026-07-23 --board-type INDUSTRY
python main.py core_market --kind board_1d --start 2026-07-01 --end 2026-07-23 \
  --board-type INDUSTRY --board-name 煤炭行业 --board-name 银行

python -m data_ingest.core_market.selfcheck
```

### CLI 要点

| 参数 | 作用 |
| --- | --- |
| `--universe TOP100` | 从已提交 Universe 快照取标的（点时用 `--universe-as-of`，默认 `--start`） |
| `--skip-existing` | 跳过已有数据：equity/adj/corp_action 看行数；按日 kind 跳过已覆盖月份 |
| `--min-bars N` | 配合 skip：行数 `< N` 才补拉；长窗回填建议 `500+`（默认 `1` 会漏补） |
| `--chunk-size` | equity/adj 分块提交；universe 或标的>30 时自动 chunked |
| `--chunk-months N` | suspend/limit/rank/异动/board：按 N 个月分块独立 commit |
| `--top-n` / `--rank-type` / `--prefer-spot` | `market_rank` |
| `--change-type` | `abnormal_move` 异动类型过滤 |
| `--board-type` / `--board-name` | `board_1d` 板块类型与名称过滤 |

### 长窗运维注意

- **停牌/涨跌停**用 `--chunk-months 1 --skip-existing`，每块独立 commit，天然断点续跑。
- 写库走 `shared/bulk_upsert`：大包分块 `executemany`，避免逐行 EXISTS 假死。
- `limit`：区间跨度 **>60 自然日** 只拉 `UP`/`DOWN`；≤60 日额外拉 `STRONG`/`ZBGC`/`PREVIOUS`/`SUB_NEW`。

### 真实源接口映射（`akshare`）

| kind | 接口 | 说明 |
| --- | --- | --- |
| `equity_1d` | `stock_zh_a_hist`（回退 `stock_zh_a_daily`） | 未复权 OHLCV |
| `adj_factor` | 同区间 `''/qfq/hfq` 收盘比 | `factor_type`=`qfq`/`hfq` |
| `suspend` | `stock_tfp_em(date)` | 按日停牌名单 |
| `limit` | `stock_zt_pool_em` + `stock_zt_pool_dtgc_em`；短窗(≤60日)另加 strong/zbgc/previous/sub_new | 长窗仅 `UP`/`DOWN`；短窗含 `STRONG`/`ZBGC`/`PREVIOUS`/`SUB_NEW` |
| `index_1d` | `stock_zh_index_daily` | 新浪指数日线 |
| `corp_action` | `stock_zh_a_daily(adjust='qfq-factor')` | P1：因子变动点近似 |
| `market_rank` | 见下表「market_rank 接口与榜型」 | 涨跌幅/量额/换手/人气排名 |
| `abnormal_move` | `ak.stock_changes_em(symbol=异动类型)` | 盘口异动；多为**最近交易日**快照，`trade_date` 取 `--end` |
| `board_1d` | `stock_board_industry_name_em` + `stock_board_industry_hist_em`；概念同理 `*_concept_*` | 默认 INDUSTRY；可用 `--board-name` 限流 |

#### market_rank 接口与榜型

实现：`sources/akshare_src.py` → `_market_rank`。库表：`raw_market_rank_1d`。

| 数据来源 | 接口 / 路径 | 何时使用 | 产出榜型 (`rank_type`) |
| --- | --- | --- | --- |
| 本地已入库日线 | SQL 读 `raw_equity_bar_1d`（`source=akshare`），按日截面算涨跌幅后排序 | **优先**：区间内该交易日已有日线 | `PCT_CHG_UP`、`PCT_CHG_DOWN`、`VOLUME`、`AMOUNT`、`TURNOVER` |
| akshare 东财实时行情 | `ak.stock_zh_a_spot_em()` | **回退**：该日库内无截面且为 `--end`/当天；或显式 `--prefer-spot` 时对 `--end`/当天优先；失败最多重试 3 次 | 同上（用「最新价/涨跌幅/成交量/成交额/换手率」字段） |
| akshare 东财人气榜 | `ak.stock_hot_rank_em()` | 请求含 `HOT`，且日期为 `--end` 或当天；失败时最多重试 3 次 | `HOT` |

说明：
- 历史区间排名依赖先跑 `equity_1d`；无日线且非当日时，该日不写榜（不强拉全市场历史现货接口）。
- `--universe` / `--symbol` 只缩小排名宇宙，不改接口；全市场不传即可。
- `--top-n` 控制每榜保留条数（默认 100）；`--rank-type` 可多选，默认全部榜型。
- `--prefer-spot`：对 `--end`/当日用全市场现货截面排名（适合补全市场榜；历史日仍走本地日线）。
- `PCT_CHG_*` 在本地路径用相邻交易日 `close` 推算涨跌幅；现货路径直接用接口「涨跌幅」。

调度建议：
```text
equity_1d ∥ adj_factor → index_1d
suspend ∥ limit（长窗按月分块）
# 可选 P1
market_rank → abnormal_move（交易日快照）
```

下游长窗示例：
```bash
python main.py data_process --p0 --universe TOP100 --universe-as-of 2026-07-23 \
  --start 2023-01-01 --end 2026-07-23 --factor-type qfq --index 000300
python main.py data_quality --scope CORE --universe TOP100 --start 2023-01-01 --end 2026-07-23 \
  --factor-type qfq --index 000300
# 交易日增量
python main.py daily --universe TOP100 --as-of 2026-07-23
```

## 不变量
- P0：`equity_1d` 与 `adj_factor` 同区间必须都可 commit，否则区间标记为 CORE 不完整
- 不在 ingest 输出「已复权日线」冒充 process
- 停牌/涨跌停以落库为准，禁止用收盘价猜测写入官方表
- 幂等键见 schema / 迁移 UNIQUE
- 长窗停牌/涨跌停用 `--chunk-months` + 批量 UPSERT；勿整窗单批
