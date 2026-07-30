# api_gateway

## 名称
对外 API / BFF：鉴权、请求聚合、统一错误码；frontend 唯一入口。

## 生产数据与落库表

| 生产数据 | 落库表 | 写入时机/说明 |
| --- | --- | --- |
| 无业务主数据 | — | 只读查询或转发命令；业务写入由领域模块落库 |
| 审计日志 | `api_audit_log` | 写操作（promote / kill / review）成功或失败后追加 |


## 本目录模块一览
无子模块；本目录即单一模块实现。辅助：`indicator_meta.py`（技术指标分类 / 主图·副图 / 线型推断）。

## 协作模块索引（供 AI Agent）

| 模块 | README | 主要作用 | 与本模块关系 |
| --- | --- | --- | --- |
| backend（父） | `../README.md` | 总览 | 父目录 |
| frontend | `../../frontend/README.md` | UI | 下游调用方 |
| strategy_registry | `../strategy_registry/README.md` | 晋升 | 写命令转发 |
| risk_engine | `../risk_engine/README.md` | Kill / 审核 | 写命令转发 |
| portfolio_construct | `../portfolio_construct/README.md` | 组合 | 只读聚合 |
| execution / ledger | `../execution` / `../ledger` | 成交/账本 | 只读聚合 |
| ops_monitor | `../ops_monitor/README.md` | 告警 | 只读 `ops_alert` |
| data_process | `../data_process/README.md` | processed 日线/指标 | 只读 `processed_equity_bar_1d` / `processed_tech_indicator_1d` |
| orchestrator | `../orchestrator/README.md` | 任务触发 | 日更仍走 CLI/schedule（本阶段未暴露启动） |

## 边界
- 做：HTTP 入口、可选 Bearer 鉴权、统一 `{ok,data,error}`、只读查询、转发晋升/Kill/风控审核。
- 不做：因子计算、撮合、过账；暴露 DB 连接；代替 risk 规则实现。

## 输入
- HTTP 请求；环境变量 `ASHARE_API_TOKEN`（可选）
- 库中已提交状态

## 输出
- JSON 信封；写操作审计 `api_audit_log`

## API（前缀 `/v1`）

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/health` | 健康检查（无鉴权） |
| GET | `/v1/strategies` | 策略列表 `?status=` |
| POST | `/v1/strategies` | 注册 DRAFT `{strategy_code, factor_code, top_n?, …}` |
| GET | `/v1/strategies/{version}` | 策略详情（含 `transitions` / `gate_results`） |
| POST | `/v1/strategies/{version}/promote` | 晋升 `{to, backtest_run?, reason?, skip_gates?, gate_version?}`；质量门失败 400 + meta.failing |
| GET | `/v1/signal/batches` | 信号批次列表 |
| POST | `/v1/signal/run` | 纸面/指定版本跑信号 `{as_of, strategy_version?, paper, live}` |
| GET | `/v1/portfolios` | 组合列表 `?status=&as_of=` |
| POST | `/v1/portfolios/build` | 构建草稿 `{as_of, strategy_version?, account_id, paper}` |
| GET | `/v1/portfolios/{id}` | 组合+持仓 |
| GET | `/v1/risk/kill` | 查询 Kill Switch |
| POST | `/v1/risk/kill` | 设置 Kill Switch `{scope, is_on, reason?}` |
| POST | `/v1/risk/review` | `{portfolio_id}` 或 `{drafts, as_of}` |
| GET | `/v1/risk/decisions` | 决策列表 |
| GET | `/v1/risk/decisions/{id}` | 决策详情（含 `breaches`） |
| GET | `/v1/executions` | 执行批次列表 `?account_id=&limit=` |
| POST | `/v1/executions/run` | 执行 `{portfolio_id}` 或 `{approved, as_of}`；默认 `adapter=paper`（禁 live_gated） |
| GET | `/v1/executions/{id}` | 执行+委托+成交 |
| GET | `/v1/execution/pending` | 残差列表 `?account_id=&status=open` |
| POST | `/v1/execution/pending/resume` | 续撮 `{as_of, account_id, adapter=paper}` |
| GET | `/v1/research/runs` | 研究运行列表 |
| GET | `/v1/research/runs/{run_id}` | 研究详情（含 `meta` / `freezes`） |
| GET | `/v1/backtest/runs` | 回测列表 `?status=&limit=` |
| POST | `/v1/backtest/runs` | 跑回测 `{strategy,start,end,universe,factor?,…}` |
| GET | `/v1/backtest/runs/{run_id}` | 回测详情（含 `nav` / `trades`） |
| GET | `/v1/market/search` | 标的搜索 `?q=&as_of=&limit=` |
| GET | `/v1/market/ranks/meta` | 榜单可用日期与类型 |
| GET | `/v1/market/ranks` | 市场榜单 `?trade_date=&rank_type=` |
| GET | `/v1/market/abnormal` | 盘口异动 |
| GET | `/v1/market/news` | 新闻/舆情 `?channel=&symbol=`（symbol 兼容纯代码 / `.SH` 后缀） |
| GET | `/v1/market/dragon-tiger` | 龙虎榜 |
| GET | `/v1/market/boards` | 板块截面 `?trade_date=&board_type=INDUSTRY|CONCEPT` |
| GET | `/v1/market/boards/history` | 板块历史 `?board_name=` |
| GET | `/v1/market/boards/members` | 行业成分 `?industry_name=` |
| GET | `/v1/market/events` | 事件日历（解禁/公司行为/合同/公告） |
| GET | `/v1/market/calendar` | 财经日历（交易日 + 宏观/政策资讯） |
| GET | `/v1/market/f10/{symbol}` | F10 资料聚合 |
| GET | `/v1/market/bars` | K 线：`?symbol=&freq=1d|15m|60m&factor_type=qfq&limit=` |
| GET | `/v1/market/indicators/meta` | 指标目录：`code/count/category/placement/style`；可按 `symbol` 过滤 |
| GET | `/v1/market/indicators` | 日线指标：`?symbol=&codes=MA_5,RSI_14&limit=180`（`processed_tech_indicator_1d` → `series`） |
| GET | `/v1/data/dq/runs` | DQ 运行列表 |
| GET | `/v1/data/dq/runs/{id}` | DQ 详情（含规则结果） |
| GET | `/v1/data/dq/gates` | DQ 门禁 |
| GET | `/v1/data/coverage` | 覆盖率矩阵 `?start=&end=` |
| GET | `/v1/ledger/accounts/{id}` | 账本；`?as_of=` 附可卖 + 市值/NAV 标记（`mark`） |
| POST | `/v1/ledger/post` | 过账 `{execution_id}` |
| GET | `/v1/ops/alerts` | 告警 |
| GET | `/v1/ops/pipeline` | 总览轻量管道状态（alerts/DQ/signal/portfolio/risk/exec/ledger） |
| GET | `/v1/modules` | 后端模块地图 + 表行数（运维台导航） |
| GET | `/v1/signal/batches/{id}` | 信号批次详情（含权重） |
| GET | `/v1/universe/snapshots` | Universe 快照列表 `?universe_code=` |
| GET | `/v1/universe/snapshots/{id}` | 快照详情（含成员） |
| GET | `/v1/data/ingest/batches` | 取数批次 `?lane=&module=` |
| GET | `/v1/execution/adapters` | 执行适配器参数 |
| GET | `/v1/research/freezes` | 证据冻结列表 |
| GET | `/v1/data/process/batches` | 加工批次 `?kind=` |
| GET | `/v1/ref/cost-params` | 费用/冲击参数版本 |
| GET | `/v1/ref/risk-limits` | 风控限额版本 |
| GET | `/v1/ref/promotion-gates` | 晋升门阈值 |
| GET | `/v1/ref/promotion-gate-results` | 晋升评估记录 |
| GET | `/v1/ledger/capital-alloc` | 策略资本配额 `?account_id=` |
| GET | `/v1/research/factors` | 因子目录（按 code×universe 聚合） |
| GET | `/v1/research/factor-defs` | 因子定义列表 `?status=`（空=全部） |
| POST | `/v1/research/factor-defs` | 注册因子 `{factor_code,template,params?}` |
| PATCH | `/v1/research/factor-defs/{code}` | 改名称/参数/状态 |
| POST | `/v1/research/runs` | 计算因子 `{factor_code,start,end,universe_code?}` |
| GET | `/v1/research/factors/{code}/values` | 因子截面 `?universe_code=&as_of=` |
| GET | `/v1/ops/audit` | API 写操作审计 |
| GET | `/v1/ops/activity` | 跨模块活动时间线 |
| POST | `/v1/ops/schedule/once` | 跑一轮日更编排 `{as_of, universe, force}`（可能耗时） |
| GET | `/v1/ledger/accounts` | 账本账户列表 |

鉴权：设置 `ASHARE_API_TOKEN` 后需 `Authorization: Bearer <token>`；未设置则开发机开放。  
生产建议：`ASHARE_API_REQUIRE_TOKEN=1`（未配置 token 时一律 401）。  
CORS：本地 `frontend/app`（Vite `:5173`）。可对 promote / kill / review 发 POST（Bearer 与只读相同）。

## 运行

```bash
cd backend
pip install -r requirements.txt   # 含 fastapi uvicorn httpx
python main.py migrate
# 推荐开发端口 8088（避免 8080 被本机代理占用）
python main.py gateway --host 127.0.0.1 --port 8088
# 文档：http://127.0.0.1:8088/docs
# 前端：cd ../frontend/app && npm run dev
curl http://127.0.0.1:8088/health
curl "http://127.0.0.1:8088/v1/market/indicators/meta"
curl "http://127.0.0.1:8088/v1/market/bars?symbol=600028&limit=5"
python -m api_gateway.selfcheck
python main.py e2e
```

## 不变量
- frontend 不得绕过本模块直连库或其他 backend 内部口（约定）
- 写操作走领域 Service，与 CLI 同口径；经库交接事实
- 不返回未授权账户数据（MVP：单 token 全局）
