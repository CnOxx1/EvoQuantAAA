# EvoQuantAAA · A 股量化系统

> **控制流归编排，数据流经落库；研究可脏，生产必版本；账本与 OMS 分离，风控可否决执行。**

远程仓库：[CnOxx1/EvoQuantAAA](https://github.com/CnOxx1/EvoQuantAAA)  
完整架构原则：[ARCHITECTURE_PRINCIPLES.md](./ARCHITECTURE_PRINCIPLES.md)

---

## 1. 项目是什么

EvoQuantAAA 是一套面向 **A 股实盘约束** 的量化研究与生产骨架：从外部数据拉取、复权加工、质量门禁、Universe、回测，一路延伸到信号晋升、组合、风控、OMS 与账本。

当前阶段重点是 **CORE 可回测闭环 + ALPHA 可插拔补数**，用真实数据源（akshare / 东财等）写入 PostgreSQL，避免 mock 污染生产库。

### 1.1 设计目标

| 目标 | 说明 |
| --- | --- |
| 真相在库 | 跨模块业务数据必须落库；下游只读已提交数据与 ID |
| CORE 先于 ALPHA | 先保证复权收益与可成交约束，再扩基本面/资金/文本 |
| 增强不拆模块 | 优先新增 `ingest_kind`，不为同类数据新建空壳模块 |
| A 股约束可回测 | 停牌/涨跌停/`can_buy`/`can_sell`、整手、费用滑点进入回测 |
| 多 Agent 可协作 | 一 Agent 一模块目录；只读对方 README 与 `database/` 契约 |

### 1.2 非目标（当前）

- 前端完整产品化 UI（`frontend/` 多为占位与规划）
- Tick / L2、宏观全量、研报全文（暂缓，见 `data_ingest/README.md`）
- 实盘柜台直连（`execution` / `ledger` 等模块尚在骨架阶段）

---

## 2. 仓库结构

```text
大a / EvoQuantAAA
├── ARCHITECTURE_PRINCIPLES.md   # 强制架构原则
├── README.md                    # 本文件：总览 + 开发更新记录
├── docker-compose.yml
├── frontend/                    # UI（不直连库，经 api_gateway）
├── backend/                     # 业务模块与 CLI 入口 main.py
│   ├── data_ingest/             # CORE / ALPHA 原始数据获取
│   ├── data_process/            # raw → processed
│   ├── data_quality/            # DQ 门禁
│   ├── security_master/         # Universe 日快照
│   ├── backtest/                # A 股约束回测
│   ├── shared/                  # DB / 配置 / Universe 解析等
│   └── …（orchestrator、research_lab、risk_engine 等骨架）
├── database/
│   ├── migrations/              # 001–013 SQL（权威演进）
│   ├── schema/                  # 产消契约说明
│   └── seeds/
└── scripts/                     # 辅助脚本
```

本地运行时数据目录 `data/`（pgembed、本地库文件）**不入库**，见 `.gitignore`。

---

## 3. 主链路

```text
外部源
  → data_ingest (raw_*, batch_id)
  → data_process (processed_*)
  → data_quality (dq_gate)
  → security_master (universe_snapshot)
  → backtest / research_lab
  → strategy_registry → signal_prod
  → portfolio_construct → risk_engine
  → execution → ledger → ops_monitor

编排：orchestrator（只传 job_id / batch_id / run_id …）
对外：api_gateway
```

### 3.1 已落地能力（可跑 CLI）

| 阶段 | 模块 | 状态摘要 |
| --- | --- | --- |
| 契约 | `database/migrations` 001–013 | 已应用 |
| CORE 参考 | `core_ref` | 日历/上市/行业/股本/成分/ST |
| CORE 行情 | `core_market` | 日线、复权、停牌、涨跌停池、指数、公司行为、市场排名、盘口异动；TOP100 长窗样本已 DQ pass |
| 加工 | `data_process` | 复权价、`ret_1d`、`can_buy`/`can_sell` |
| 门禁 | `data_quality` | CORE 规则 + `dq_gate` |
| Universe | `security_master` | 默认 `TOP100` / `SECTOR_LEADERS`（全市场仅按需） |
| 回测 | `backtest` | `EW_HOLD` + 成本参数 + NAV/成交 |
| ALPHA | announcement / fundamental / flow / news | 真实源可入库（覆盖按需扩） |

### 3.2 骨架/待建

`orchestrator`、`research_lab`、`signal_prod`、`strategy_registry`、`portfolio_construct`、`risk_engine`、`execution`、`ledger`、`ops_monitor`、`api_gateway`、多数 `frontend/*`。

---

## 4. 数据与存储

- **默认库**：PostgreSQL（`pgembed` 本地嵌入式，数据在 `data/pgdata`；也可用 `ASHARE_DATABASE_URL`）
- **已弃用**：SQLite `data/ashare.db`（勿再作为生产路径）
- **批次**：`ingest_batch` / `process_batch`；回测 `backtest_run`；DQ `dq_run` / `dq_gate`
- **原则**：mock 仅调试；生产路径使用真实源；禁止把 mock 批次当正式样本

权威表与产消关系见 [`database/schema/README.md`](./database/schema/README.md) 与各模块 README。

---

## 5. 快速开始

```bash
cd backend
pip install -r requirements.txt

# 迁移
python main.py migrate

# CORE 参考 + 行情（示例）
python main.py core_ref --p0 --start 2026-07-01 --end 2026-07-31 --source akshare
# Universe：仅 TOP100 + 行业龙头（不全市场）
python main.py security_master --p0 --as-of 2026-07-23

# 长窗 CORE（推荐）：日历 + TOP100 日线/复权
python main.py core_ref --kind calendar --start 2020-01-01 --end 2026-07-25
python main.py core_market --p0 --universe TOP100 --start 2023-01-01 --end 2026-07-23 --skip-existing --min-bars 500 --chunk-size 8 --index 000300
python main.py core_market --kind index_1d --start 2023-01-01 --end 2026-07-23 --index 000300 --index 000905 --index 000852

# 市场排名（涨跌幅/量额/换手/人气；接口见 core_market README）
python main.py core_market --kind market_rank --start 2026-07-01 --end 2026-07-23 --top-n 200
python main.py core_market --kind market_rank --start 2026-07-23 --end 2026-07-23 --top-n 200 --prefer-spot

# 加工 → 门禁 → 回测（长窗）
python main.py data_process --p0 --universe TOP100 --universe-as-of 2026-07-23 --start 2023-01-01 --end 2026-07-23 --factor-type qfq --index 000300
python main.py data_quality --scope CORE --start 2023-01-01 --end 2026-07-23 --factor-type qfq --index 000300
python main.py backtest --universe TOP100 --start 2023-01-01 --end 2026-07-23 --strategy EW_HOLD --factor-type qfq

# 非龙头个股：按需单票
python main.py core_market --kind equity_1d --start 2026-07-01 --end 2026-07-23 --symbol 600519
```

更多子命令与 kind 说明：

- [`backend/README.md`](./backend/README.md)
- [`backend/data_ingest/README.md`](./backend/data_ingest/README.md)
- [`backend/data_ingest/core_market/README.md`](./backend/data_ingest/core_market/README.md)（含 `market_rank` 接口映射）

常用 ALPHA / P1 示例：

```bash
python main.py alpha_announcement --kind ann_watchlist --symbol 600000 --start 2024-08-01 --end 2024-08-16 --source eastmoney --no-fallback
python main.py alpha_fundamental --p1 --symbol 600000 --symbol 000001
python main.py alpha_flow --p1 --start 2024-08-01 --end 2024-08-16 --symbol 600000
python main.py alpha_flow --kind margin --start 2024-07-08 --end 2024-07-12 --symbol 600000 --symbol 000001
python main.py core_market --kind corp_action --start 2020-01-01 --end 2026-07-23 --symbol 600000
python main.py core_market --kind market_rank --start 2026-07-23 --end 2026-07-23 --top-n 200 --prefer-spot --rank-type HOT
python main.py core_market --kind abnormal_move --start 2026-07-23 --end 2026-07-23
python main.py core_market --kind limit --start 2026-07-21 --end 2026-07-23
python main.py alpha_flow --kind dragon_tiger --start 2026-07-01 --end 2026-07-23
python main.py alpha_flow --kind dragon_tiger_seat --start 2026-07-01 --end 2026-07-23
python main.py alpha_flow --kind block_trade --start 2026-07-01 --end 2026-07-23
```

---

## 6. 协作约定（多 AI Agent）

- **一个 Agent 只写一个模块目录**，禁止越界改其他模块实现。
- 了解协作：只读对方 `README.md` 与 `database/` 契约。
- 跨模块：先落库，再传 `batch_id` / `job_id` / `run_id` / `strategy_version` 等引用。
- 调度只通过 `orchestrator`；对外 API 只经 `api_gateway`。
- 新增模块或表：更新本文件「开发更新记录」、相关 README，并遵守 [ARCHITECTURE_PRINCIPLES.md §6](./ARCHITECTURE_PRINCIPLES.md#6-合入前检查清单)。

---

## 7. 开发更新记录

> 维护约定：有可合并的功能/数据里程碑时，在本节**顶部**追加一条（新→旧）。  
> 格式：日期 · 标题 · 要点列表 ·（可选）影响范围。

### 2026-07-25 · ingest 工程优化 + 四个增强 kind

- **工程**：`shared/bulk_upsert` 分块 executemany；`shared/akshare_call` 统一重试/降噪；`chunk_date_ranges` + `--chunk-months` + 按日 skip-existing（取代临时月分块脚本）
- **入口**：`python main.py daily --universe TOP100`（交易日增量 CORE→process→DQ；`--with-alpha` 含估值/龙虎榜）；`data_quality --universe`
- **新 kind**（迁移 `013_ingest_enhancements.sql`）：
  - `core_market.board_1d` → `raw_board_bar_1d`（行业/概念板块日线）
  - `alpha_fundamental.valuation` → `raw_valuation_1d`（`stock_value_em` PE/PB/市值）
  - `alpha_fundamental.holder` → `raw_holder_count`（股东户数）
  - `core_ref.restricted_release` → `raw_restricted_release`（限售解禁）
- 仍不新建空模块；接口与 CLI 见各子目录 README

### 2026-07-25 · P0 长窗 CORE：TOP100 2023–2026

- `calendar`：2020-01-01～2026-07-31（~2400 日）
- `TOP100`：`equity_1d`/`adj_factor` 约 **860 交易日/票**（2023-01～2026-07）；指数 000300/000905/000852 同窗
- CLI：`--min-bars` 配合 `--skip-existing` 做长窗增量；大包 upsert 去掉逐行 EXISTS，避免停牌长窗卡死
- `limit` 长窗（>60 日）仅拉 UP/DOWN；短窗仍含强势/炸板等扩展池
- `data_process --p0 --universe TOP100`：processed equity **~85.9k** + index 860
- `data_quality --scope CORE`：**passed**（`dq_7da7af1f279a4151b0c0bd997a35a010`）
- 停牌/涨跌停：改为**按月分块**续跑（全窗一次拉 66 万行再 upsert 会假死）

### 2026-07-25 · 异动 / 龙虎榜席位 / 涨停池扩展

- 新增 `core_market.abnormal_move` → `raw_abnormal_move`（`ak.stock_changes_em` 盘口异动；多为最近交易日快照）
- 新增 `alpha_flow.dragon_tiger_seat` → `raw_dragon_tiger_seat`（`ak.stock_lhb_hyyyb_em` 每日活跃营业部）
- 扩展 `core_market.limit`：除 UP/DOWN 外增加 `STRONG`/`ZBGC`/`PREVIOUS`/`SUB_NEW` 池
- 迁移 `012_market_microstructure.sql`
- 样本入库（`2026-07-01`–`23`）：龙虎榜约 1.8k、营业部约 4.6k、大宗约 1.7k；涨停扩展池约 1.2k；盘口异动约 **9.5k**

### 2026-07-25 · core_market 市场排名（涨跌幅/量额等）

- 新增 `ingest_kind=market_rank` → 表 `raw_market_rank_1d`（迁移 `011_market_rank.sql`）
- 榜型：`PCT_CHG_UP` / `PCT_CHG_DOWN` / `VOLUME` / `AMOUNT` / `TURNOVER` / `HOT`
- 接口：优先本地 `raw_equity_bar_1d` 截面排序；缺截面回退 `ak.stock_zh_a_spot_em()`；人气榜 `ak.stock_hot_rank_em()`（详见 [`core_market/README.md`](./backend/data_ingest/core_market/README.md)）
- CLI：`--top-n`、`--rank-type`、`--prefer-spot`；可选 `--universe` 缩小排名宇宙
- 样本入库：`2026-07-01`–`2026-07-23` 共 **16600** 行（约 17 交易日 × 量额/换手等榜 × top200；首日无昨收故无涨跌幅榜）
- 东财现货/人气接口近期偶发断连；`--prefer-spot` / `HOT` 可在交易时段重试补全
- 量化用途：动量/拥挤度筛选、异常量能、短线热度；建议在 `equity_1d` 之后跑

### 2026-07-25 · 本地只沉淀龙头，其余按需 API

- 策略调整：**不对 6000+ 全市场 bulk 落库**；默认 Universe 改为 `TOP100` + `SECTOR_LEADERS`
- `security_master --p0`：生成 Top100（股本×收盘/股本）与各行业 1 只龙头
- Ingest/文档默认改为 `--universe TOP100`；非龙头用 `--symbol` 按需拉取
- `ALL_LISTED` / `HS300` 仍可选，但不作为默认灌数范围

### 2026-07-24 · Ingest 分块续跑优化

- 新增 `shared/ingest_batching.py`：`chunk_symbols` / `resolve_symbols_from_args` / `should_chunk`
- `core_market`：单 kind（含 `corp_action`）支持分块；`--skip-existing` 对 corp_action 按 `ex_date` 跳过
- `alpha_fundamental`：`--universe` / `--chunked` / `--chunk-size` / `--skip-existing`；`run_p1_chunked`
- `alpha_flow`：`--universe` / 分块；`run_p1_chunked`（northbound + stock_flow 分块）
- 单 chunk 失败不中断后续块，便于 HS300 增量补数

### 2026-07-24 · 首推 GitHub 与主文档

- 初始化 git，推送到 [CnOxx1/EvoQuantAAA](https://github.com/CnOxx1/EvoQuantAAA)（`main`）
- 根 README 扩充为项目总览 + 本更新记录
- `.gitignore`：忽略 `data/`、`_tmp*` 等本地数据与临时文件

### 2026-07-24 · ALPHA 空表补齐与现有模块加深

- **不新建模块**：公告/公司行为/两融/大宗/基本面均在既有域用 `ingest_kind` 补齐
- `core_market.corp_action` 加深：`DIVIDEND` / `BONUS` / `RIGHTS` + 复权因子**变动点**（不再按日灌因子）
- `alpha_flow.margin` 加深：上交所 + **深交所**市场汇总与个股明细（`MARKET_SZSE`）
- 真实入库（样本）：公告约 7k 行；财报/指标；一致预期 EPS；北向资金流；两融；大宗；公司行为含分红/送转

### 2026-07-24 · HS300 CORE 闭环与回测

- 修复 `core_ref` 指数成分字段误匹配（避免全体变成指数代码）
- `core_market` / `data_process` 支持 `--universe`；行情分块 `--chunked` / `--skip-existing`
- HS300 区间日线+复权覆盖 **300/300**；`data_process` → CORE `dq_gate=passed` → `EW_HOLD` 回测
- 回测样本：策略约 +2.48% vs 沪深300 约 -4.66%；建仓覆盖 178/300（100 万等权整手约束，非缺行情）

### 2026-07-24 · 加工 / DQ / Universe / 回测模块落地

- 迁移 `007_data_process`：`processed_equity_bar_1d` / `processed_index_bar_1d` / `process_batch`
- 迁移 `008_data_quality`：`dq_run` / `dq_result` / `dq_gate`
- 迁移 `009_security_master`：`universe_snapshot` + members（`ALL_LISTED` / `HS300` / `HS300_EX_ST`）
- 迁移 `010_backtest`：`cost_params` / `backtest_run` / `backtest_nav` / `backtest_trade`；策略 `EW_HOLD`

### 2026-07-24 及前期 · CORE/ALPHA ingest 与 PG 底座

- 默认存储切换为 PostgreSQL（pgembed）；SQLite 路径弃用
- 迁移 `001`–`006`：公告、参考、行情、基本面、资金流、新闻
- `data_ingest` 域划分：`core_ref` / `core_market` / `alpha_fundamental` / `alpha_flow` / `alpha_announcement` / `alpha_news_monitor`
- CLI 统一入口：`backend/main.py`
- 清理 PG 中 mock 污染数据；坚持真实源优先

---

## 8. 文档索引

| 文档 | 内容 |
| --- | --- |
| [ARCHITECTURE_PRINCIPLES.md](./ARCHITECTURE_PRINCIPLES.md) | 强制架构、产消、合入检查 |
| [backend/README.md](./backend/README.md) | 后端模块一览与运行入口 |
| [backend/data_ingest/README.md](./backend/data_ingest/README.md) | ingest 阶段与 kind 清单 |
| [backend/data_ingest/core_market/README.md](./backend/data_ingest/core_market/README.md) | 行情 kinds 与 akshare 接口映射 |
| [database/README.md](./database/README.md) | 迁移与契约 |
| [frontend/README.md](./frontend/README.md) | 前端边界 |

---

## 9. 许可与贡献

内部/私有项目协作时：先开分支，更新「开发更新记录」与相关模块 README，再合入 `main`。  
合入前检查见架构原则 §6。
