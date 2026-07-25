# alpha_contract

## 名称
量化 ALPHA · **上市公司重大合同 / 中标信息**获取：落库供订单/中标事件研究（不阻塞 CORE）。

## 生产数据与落库表

| 生产数据 | 落库表 | 写入时机/说明 |
| --- | --- | --- |
| 重大合同 / 中标明细 | `raw_major_contract` | `win_bid` / `major_contract` |
| 批次 | `ingest_batch` | 经 ingest_common |

迁移：`015_alpha_contract.sql`。  
与法定公告（`alpha_announcement`）分表：本模块存结构化合同字段（金额、对手方、类型），公告模块存披露原文元数据。

### 关键字段

| 字段 | 含义 |
| --- | --- |
| `announce_date` | 公告日（点时，策略只用此日） |
| `contract_type` / `contract_name` | 合同类型 / 名称 |
| `amount` / `amount_rev_ratio` | 合同金额、占上年营收比 |
| `party_self` / `party_other` | 签署主体 / 其他签署方 |
| `is_win_bid` | 1=中标类（类型或名称含中标/中选/成交） |

## 本目录模块一览

| ingest_kind | 优先级 | 输出表 | 说明 |
| --- | --- | --- | --- |
| `win_bid` | P1 | `raw_major_contract` | **仅中标相关**行（推荐日常增量） |
| `major_contract` | P1 | `raw_major_contract` | 东财重大合同全量（含销售/工程建设等） |

## 运行

```bash
cd backend
python main.py migrate

# 中标（短窗冒烟）
python main.py alpha_contract --kind win_bid --start 2026-07-01 --end 2026-07-25

# 重大合同全量 + Universe 过滤
python main.py alpha_contract --kind major_contract --start 2026-07-01 --end 2026-07-25 --universe TOP100

# 单票
python main.py alpha_contract --kind win_bid --start 2026-07-01 --end 2026-07-25 --symbol 600284

python -m data_ingest.alpha_contract.selfcheck
```

### 真实源接口映射（`akshare`）

| kind | 接口 | 说明 |
| --- | --- | --- |
| `win_bid` / `major_contract` | `stock_zdhtmx_em` | 东财数据中心-重大合同明细；`win_bid` 在入库前按类型/名称过滤中标 |

说明：
- 公开源无独立「全市场中标库」时，以东财重大合同中的「项目中标」及名称含中标关键词的条目作为中标原料。
- **双源交叉**：法定披露侧用  
  `python main.py alpha_announcement --kind ann_by_category --category win_bid --start … --end …`  
  落 `raw_announcement`（`category_norm=win_bid`），与本表按标的+公告日对齐补漏。
- 点时一律用 `announce_date`，禁止用 `ingested_at`。
- 开发机请用短日期窗；长窗回填放到非开发机。

## 不变量
- 幂等：`(symbol, announce_date, source_event_id, source)`
- ALPHA 失败不阻塞 CORE
- 不与 `raw_announcement` 混表
