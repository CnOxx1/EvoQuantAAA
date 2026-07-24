# alpha_flow

## 名称
量化 ALPHA · 资金与交易活跃度原料：北向/个股资金，以及两融、龙虎榜、大宗（增强 kind）。

## 生产数据与落库表

| 生产数据 | 落库表 | 写入时机/说明 |
| --- | --- | --- |
| 资金流向 | `raw_money_flow` | kind=`northbound` / `stock_flow` |
| 融资融券 | `raw_margin` | kind=`margin`（P2） |
| 龙虎榜 | `raw_dragon_tiger` | kind=`dragon_tiger`（P2） |
| 大宗交易 | `raw_block_trade` | kind=`block_trade`（P2） |
| 批次 | `ingest_batch` | 经 ingest_common |

迁移脚本：`database/migrations/005_alpha_flow.sql`。

## 本目录模块一览

| ingest_kind | 优先级 | 输出表 | 量化用途 |
| --- | --- | --- | --- |
| `northbound` | P1 | `raw_money_flow` | 北向类因子（`NORTHBOUND`/`_SH`/`_SZ`） |
| `stock_flow` | P1 | `raw_money_flow` | 个股资金（`STOCK_FLOW` / 回退 `STOCK_NORTHBOUND`） |
| `margin` | P2 | `raw_margin` | 融资融券余额/标的 |
| `dragon_tiger` | P2 | `raw_dragon_tiger` | 龙虎榜情绪/席位 |
| `block_trade` | P2 | `raw_block_trade` | 大宗交易折溢价 |

## 协作模块索引（供 AI Agent）

| 模块 | README | 主要作用 | 与本模块关系 |
| --- | --- | --- | --- |
| data_ingest（父） | `../README.md` | 总览 | 父目录 |
| ingest_common | `../ingest_common/README.md` | batch | 可引用 |
| core_market | `../core_market/README.md` | CORE | 不阻塞、不互相 import |
| research_lab | `../../research_lab/README.md` | 资金/情绪因子 | 下游 |

## 边界
- 做：按主题落 raw，记录滞后/可得时点。
- 不做：编造补全；阻塞 CORE；与公告/新闻混表。

## 运行

```bash
cd backend
python main.py migrate
python main.py alpha_flow --p1 --start 2024-08-01 --end 2024-08-16 --symbol 600000
python main.py alpha_flow --kind northbound --start 2024-08-01 --end 2024-08-16
python main.py alpha_flow --kind stock_flow --start 2024-08-01 --end 2024-08-16 --symbol 600000
python main.py alpha_flow --kind margin --start 2026-07-01 --end 2026-07-23 --symbol 600000
python main.py alpha_flow --kind dragon_tiger --start 2026-07-21 --end 2026-07-23
python main.py alpha_flow --kind block_trade --start 2026-07-21 --end 2026-07-23
python -m data_ingest.alpha_flow.selfcheck
```

### 真实源接口映射（`akshare`）

| kind | 接口 | 说明 |
| --- | --- | --- |
| `northbound` | `stock_hsgt_hist_em` | 北向/沪股通/深股通；金额转元 |
| `stock_flow` | `stock_individual_fund_flow`（回退 `stock_hsgt_individual_em`） | 个股主力/北向增持 |
| `margin` | `stock_margin_sse` + `stock_margin_detail_sse` | 市场汇总 + 标的明细 |
| `dragon_tiger` | `stock_lhb_detail_em` | 按区间 |
| `block_trade` | `stock_dzjy_mrmx` | A股大宗明细 |

说明：东财北向历史「净买额」约在 2024-08 后停更；请求近区间无有效值时会回退最近有效交易日，并在日志告警。

## 不变量
- 资金流幂等：`(scope, trade_date, flow_type, source)`
- 两融幂等：`(symbol, trade_date, source)`
- 龙虎榜/大宗：含 `trade_date` + `source_event_id`
- ALPHA 失败不得影响 CORE
