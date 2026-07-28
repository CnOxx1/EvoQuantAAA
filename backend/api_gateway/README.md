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
| GET | `/v1/strategies/{version}` | 策略详情 |
| POST | `/v1/strategies/{version}/promote` | 晋升 `{to, backtest_run?, reason?, skip_gates?, gate_version?}`；质量门失败 400 + meta.failing |
| GET | `/v1/portfolios` | 组合列表 |
| GET | `/v1/portfolios/{id}` | 组合+持仓 |
| GET | `/v1/risk/kill` | 查询 Kill Switch |
| POST | `/v1/risk/kill` | 设置 Kill Switch `{scope, is_on, reason?}` |
| POST | `/v1/risk/review` | `{portfolio_id}` 或 `{drafts, as_of}` |
| GET | `/v1/risk/decisions` | 决策列表 |
| GET | `/v1/executions` | 执行批次列表 `?account_id=&limit=` |
| GET | `/v1/executions/{id}` | 执行+委托+成交 |
| GET | `/v1/execution/pending` | 残差列表 `?account_id=&status=open` |
| GET | `/v1/research/runs` | 研究运行列表 |
| GET | `/v1/market/ranks/meta` | 榜单可用日期与类型 |
| GET | `/v1/market/ranks` | 市场榜单 `?trade_date=&rank_type=` |
| GET | `/v1/market/abnormal` | 盘口异动 |
| GET | `/v1/market/news` | 新闻/舆情 `?channel=&symbol=`（symbol 兼容纯代码 / `.SH` 后缀） |
| GET | `/v1/market/dragon-tiger` | 龙虎榜 |
| GET | `/v1/market/bars` | 日线 K：`?symbol=&start=&end=&factor_type=qfq&limit=120`（`processed_equity_bar_1d`；symbol 归一化为纯代码） |
| GET | `/v1/market/indicators/meta` | 指标目录：`code/count/category/placement/style`；可按 `symbol` 过滤 |
| GET | `/v1/market/indicators` | 日线指标：`?symbol=&codes=MA_5,RSI_14&limit=180`（`processed_tech_indicator_1d` → `series`） |
| GET | `/v1/ledger/accounts/{id}` | 账本；`?as_of=` 附可卖 |
| GET | `/v1/ops/alerts` | 告警 |

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
