# alpha_fundamental

## 名称
量化 ALPHA · 基本面原料：财报/财务指标，以及卖方一致预期（先以 kind 承载，不单拆模块）。

## 生产数据与落库表

| 生产数据 | 落库表 | 写入时机/说明 |
| --- | --- | --- |
| 财务报表原值（长表科目） | `raw_fund_statement` | kind=`statement` |
| 财务指标 | `raw_fund_indicator` | kind=`indicator` |
| 一致预期 | `raw_consensus_estimate` | kind=`consensus`（P2） |
| 日频估值 | `raw_valuation_1d` | kind=`valuation`（P1） |
| 股东户数 | `raw_holder_count` | kind=`holder`（P2） |
| 批次 | `ingest_batch` | 经 ingest_common |

迁移脚本：`004_alpha_fundamental.sql`、`013_ingest_enhancements.sql`。

## 本目录模块一览
无子模块；按 `ingest_kind` 拉数。

| ingest_kind | 优先级 | 输出表 | 量化用途 |
| --- | --- | --- | --- |
| `statement` | P1 | `raw_fund_statement` | 报表因子 |
| `indicator` | P1 | `raw_fund_indicator` | 估值/质量等指标原料 |
| `valuation` | P1 | `raw_valuation_1d` | PE/PB/PS/市值日频（估值因子） |
| `consensus` | P2 | `raw_consensus_estimate` | 盈利预测/一致预期（PIT） |
| `holder` | P2 | `raw_holder_count` | 股东户数/筹码集中度 |

## 协作模块索引（供 AI Agent）

| 模块 | README | 主要作用 | 与本模块关系 |
| --- | --- | --- | --- |
| data_ingest（父） | `../README.md` | 总览 | 父目录 |
| ingest_common | `../ingest_common/README.md` | batch | 可引用 |
| core_market | `../core_market/README.md` | 价量 CORE | 不依赖本域 |
| alpha_announcement | `../alpha_announcement/README.md` | 预告/快报等披露事件 | 同级；事件在公告，数值在本模块 |
| research_lab | `../../research_lab/README.md` | 基本面/预期因子 | 下游 |
| database/schema | `../../../database/schema/README.md` | 契约 | 上游 |

## 边界
- 做：落库报表期、公告日、科目/指标/预期与版本。
- 不做：因子计算；用最新财报/预期回刷历史时点；阻塞 CORE。

## 运行

```bash
cd backend
pip install -r requirements.txt
python main.py migrate
# 默认 --source akshare
python main.py alpha_fundamental --p1 --symbol 600000
python main.py alpha_fundamental --kind statement --symbol 600000 --statement-type INCOME --start 2024-01-01 --end 2026-07-24
python main.py alpha_fundamental --kind indicator --symbol 600000 --symbol 000001
python main.py alpha_fundamental --kind consensus --symbol 600000
python main.py alpha_fundamental --kind valuation --universe TOP100 \
  --start 2026-07-01 --end 2026-07-23 --chunk-size 10
python main.py alpha_fundamental --kind holder --universe TOP100 --chunk-size 10
python -m data_ingest.alpha_fundamental.selfcheck
```

### 真实源接口映射（`akshare`）

| kind | 接口 | 说明 |
| --- | --- | --- |
| `statement` | `stock_*_sheet_by_report_em` | INCOME/BALANCE/CASHFLOW → 长表 `item_code` |
| `indicator` | `stock_financial_analysis_indicator_em`（回退新浪指标） | 按报告期 |
| `valuation` | `stock_value_em` | 东财日频估值（不用已失效的 `stock_a_indicator_lg`） |
| `consensus` | `stock_profit_forecast_em`（回退同花顺逐票） | `asof_date`=拉取日；`version`=同日 |
| `holder` | `stock_zh_a_gdhs_detail_em` | 个股股东户数历史；可按 start/end 过滤截止日 |

调度：P1 `statement` / `indicator`（CORE+DQ 后）；P2 `consensus` 按需。失败不影响 CORE。

## 不变量
- 报表：`announce_date` / `report_period` 必有
- 预期：必须有 `asof_date`，禁止只用「最新一致预期」无历史
- 幂等含披露/预测版本（见 UNIQUE）
- 默认跳过 `*_YOY` 科目以控制体积；需要同比可改源参数
