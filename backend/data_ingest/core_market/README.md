# core_market

## 名称
量化 CORE · 市场数据心脏：未复权行情 + 复权因子 + 停牌/涨跌停 + 指数基准（同域强制齐套）。

## 生产数据与落库表

| 生产数据 | 落库表 | 写入时机/说明 |
| --- | --- | --- |
| 股票日线 | `raw_equity_bar_1d` | kind=`equity_1d` |
| 复权因子 | `raw_adj_factor` | kind=`adj_factor`（`qfq`/`hfq`） |
| 停牌 | `raw_suspend` | kind=`suspend` |
| 涨跌停 | `raw_limit_board` | kind=`limit`（`UP`/`DOWN`） |
| 指数日线 | `raw_index_bar_1d` | kind=`index_1d` |
| 公司行为 | `raw_corp_action` | kind=`corp_action`（P1） |
| 批次 | `ingest_batch` | 经 ingest_common |

迁移脚本：`database/migrations/003_core_market.sql`。

## 本目录模块一览
无子模块；按 `ingest_kind` 拉数。**策略侧不得在缺少 adj/suspend/limit 时单独宣称 equity_1d 可用。**

| ingest_kind | 优先级 | 输出表 | 量化用途 |
| --- | --- | --- | --- |
| `equity_1d` | P0 | `raw_equity_bar_1d` | 价量（未复权） |
| `adj_factor` | P0 | `raw_adj_factor` | 除权后收益 |
| `suspend` | P0 | `raw_suspend` | 停牌不可成交 |
| `limit` | P0 | `raw_limit_board` | 涨跌停约束 |
| `index_1d` | P0 | `raw_index_bar_1d` | 基准/相对收益 |
| `corp_action` | P1 | `raw_corp_action` | 复权校验、事件 |
| `equity_1m` | P2 | （未实现） | 日内 |

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
# 默认 --source akshare
python main.py core_market --p0 --start 2026-07-21 --end 2026-07-23 --symbol 600000 --symbol 000001 --index 000300
python main.py core_market --kind equity_1d --start 2026-07-01 --end 2026-07-23 --symbol 600000
python main.py core_market --kind adj_factor --start 2026-07-01 --end 2026-07-23 --symbol 600000
python main.py core_market --p0 --start 2026-07-01 --end 2026-07-23 --universe HS300 --skip-existing --chunk-size 15
python main.py core_market --kind suspend --start 2026-07-21 --end 2026-07-23
python main.py core_market --kind limit --start 2026-07-21 --end 2026-07-23
python main.py core_market --kind index_1d --start 2026-07-01 --end 2026-07-23 --index 000300
python -m data_ingest.core_market.selfcheck
```

### 真实源接口映射（`akshare`）

| kind | 接口 | 说明 |
| --- | --- | --- |
| `equity_1d` | `stock_zh_a_hist`（回退 `stock_zh_a_daily`） | 未复权 OHLCV |
| `adj_factor` | 同区间 `''/qfq/hfq` 收盘比 | `factor_type`=`qfq`/`hfq` |
| `suspend` | `stock_tfp_em(date)` | 按日停牌名单 |
| `limit` | `stock_zt_pool_em` + `stock_zt_pool_dtgc_em` | UP / DOWN |
| `index_1d` | `stock_zh_index_daily` | 新浪指数日线 |
| `corp_action` | `stock_zh_a_daily(adjust='qfq-factor')` | P1：因子变动点近似 |

调度建议：
```text
equity_1d ∥ adj_factor → suspend ∥ limit → index_1d
```

## 不变量
- P0：`equity_1d` 与 `adj_factor` 同区间必须都可 commit，否则区间标记为 CORE 不完整
- 不在 ingest 输出「已复权日线」冒充 process
- 停牌/涨跌停以落库为准，禁止用收盘价猜测写入官方表
- 幂等键见 schema / 迁移 UNIQUE
