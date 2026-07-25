# core_ref

## 名称
量化 CORE · 参考数据：交易日历、上市状态、行业/股本，以及指数成分与 ST 状态史（增强 kind）。

## 生产数据与落库表

| 生产数据 | 落库表 | 写入时机/说明 |
| --- | --- | --- |
| 交易日历 | `raw_trade_calendar` | kind=`calendar` |
| 上市/退市原料 | `raw_security_listing` | kind=`listing` |
| 行业分类 | `raw_industry_class` | kind=`industry` |
| 股本 | `raw_share_capital` | kind=`share_capital` |
| 指数成分权重 | `raw_index_member` | kind=`index_member`（P1） |
| ST 等状态史 | `raw_special_treat` | kind=`special_treat`（P1） |
| 限售解禁 | `raw_restricted_release` | kind=`restricted_release`（P1） |
| 批次 | `ingest_batch` | 经 ingest_common |


## 本目录模块一览
无子模块；按 `ingest_kind` 拉数。

| ingest_kind | 优先级 | 输出表 | 量化用途 |
| --- | --- | --- | --- |
| `calendar` | P0 | `raw_trade_calendar` | 交易日对齐 |
| `listing` | P0 | `raw_security_listing` | 上市/退市/板块，防未来股票 |
| `industry` | P0 | `raw_industry_class` | 行业中性、行业暴露 |
| `share_capital` | P0 | `raw_share_capital` | 市值、换手、权重 |
| `index_member` | P1 | `raw_index_member` | 指数成分与权重时序（指数增强） |
| `special_treat` | P1 | `raw_special_treat` | ST/*ST/退市整理等状态变更史 |
| `restricted_release` | P1 | `raw_restricted_release` | 解禁日历（事件风险过滤） |

## 协作模块索引（供 AI Agent）

| 模块 | README | 主要作用 | 与本模块关系 |
| --- | --- | --- | --- |
| data_ingest（父） | `../README.md` | 总览 | 父目录 |
| ingest_common | `../ingest_common/README.md` | batch | 可引用 |
| core_market | `../core_market/README.md` | 行情 CORE | 同级；日历对齐行情 |
| security_master | `../../security_master/README.md` | Universe 快照 | 主下游（含 ST/成分过滤） |
| database/schema | `../../../database/schema/README.md` | 契约 | 上游 |

## 边界
- 做：落库参考原料，保留点时/生效日；成分权重按指数+日期落库。
- 不做：产出正式 Universe 快照（security_master）；行情与复权。

## 输入
交易所、日期/生效区间、指数代码、分类标准（如申万/中信，写入元数据）；`job_id` + kind

## 输出
对应 `raw_*` + `batch_id`

## 运行

```bash
cd backend
pip install -r requirements.txt
python main.py migrate
# 默认 --source akshare（真实公开接口）
python main.py core_ref --p0 --start 2026-07-01 --end 2026-07-31
python main.py core_ref --kind calendar --start 2026-07-01 --end 2026-07-31
python main.py core_ref --kind listing
python main.py core_ref --kind industry --industry-standard SW2021
python main.py core_ref --kind share_capital --share-sh-limit 80
python main.py core_ref --kind index_member --index 000300
python main.py core_ref --kind special_treat
python main.py core_ref --kind restricted_release --start 2026-07-01 --end 2026-07-23
python main.py core_ref --kind restricted_release --start 2026-07-01 --end 2026-07-23 \
  --universe TOP100
# 离线夹具
python main.py core_ref --kind listing --source mock
python -m data_ingest.core_ref.selfcheck
```

### 真实源接口映射（`akshare`）

| kind | 接口 | 说明 |
| --- | --- | --- |
| `calendar` | `tool_trade_date_hist_sina` | 区间内逐日标记 is_open |
| `listing` | `stock_info_sh/sz/bj_name_code` + 退市列表 | 含板块、上市/退市日 |
| `industry` | `sw_index_first_info` + `index_component_sw` | 标准名以 `SW` 开头；否则用深/北所属行业 |
| `share_capital` | 深/北列表股本 + `stock_zh_a_gbjg_em`（沪） | 沪市默认 `--share-sh-limit 80`，`0`=全量 |
| `index_member` | `index_stock_cons_csindex`（回退 `index_stock_cons`） | 无权重时按等权占位 |
| `special_treat` | `stock_zh_a_st_em`（回退名称含 ST） | 快照生效日=拉取日 |
| `restricted_release` | `stock_restricted_release_detail_em`；有 `--symbol`/`--universe` 时再补 `stock_restricted_release_queue_em` | 按解禁日区间；可过滤龙头 |

调度建议：
- P0 日更：`calendar` → `listing` → `industry` ∥ `share_capital`（或 `--p0`）
- P1：`special_treat`；`index_member`（按指数配置）；`restricted_release` 按区间

实现入口：`service.CoreRefIngestService`；总入口：`backend/main.py`。  
默认源：`akshare`；离线联调用 `--source mock`。

## 不变量
- listing/industry/share/ST/成分必须可历史回溯，禁止仅「最新一份」
- 行业标准、指数代码与版本写入 batch/行元数据
- `index_member` 幂等建议：`(index_symbol, symbol, trade_date, source)`（权重变更按日）
- `special_treat` 幂等建议：`(symbol, effective_date, treat_type, source)`
