# execution

## 名称
交易执行（OMS）：消费**已风控放行**的目标持仓；纸面适配器即时成交；只写订单/成交**事件**（不过账）；未成交残差入 **pending** 下日续撮。

## 生产数据与落库表

| 生产数据 | 落库表 | 写入时机/说明 |
| --- | --- | --- |
| 执行批次 | `execution_run` | `run_kind=portfolio\|pending_resume`；portfolio 类同 portfolio 至多一 committed |
| 委托事件 | `order_event` | NEW / STATUS（FILLED/REJECTED） |
| 成交事件 | `fill_event` | 纸面即时成交；含佣金/印花税/滑点 |
| 未成交残差 | `execution_pending` | 意图−成交≥1 手 → `open`；续撮削减或 `filled`；新调仓 `superseded` |
| 残差审计 | `execution_pending_event` | 每次续撮 qty_before/after |


## 本目录模块一览

| 路径 | 作用 |
| --- | --- |
| `paper.py` | 意图 / 纸面撮合 / 残差（纯函数） |
| `adapters/` | 可插拔执行适配器：`paper`、`broker_stub`、`live_gated` |
| `service.py` | portfolio run + resume_pending |

## 协作模块索引（供 AI Agent）

| 模块 | README | 主要作用 | 与本模块关系 |
| --- | --- | --- | --- |
| backend（父） | `../README.md` | 总览 | 父目录 |
| database | `../../database/README.md` | 订单事件表 | 上游契约 |
| risk_engine | `../risk_engine/README.md` | 放行/Kill Switch | 上游硬依赖（经库）；续撮仅查 Kill |
| portfolio_construct | `../portfolio_construct/README.md` | 目标持仓 | 间接上游 |
| ledger | `../ledger/README.md` | 账本过账 | 下游；CLI 每单立即 post（无 fill 跳过） |
| ops_monitor | `../ops_monitor/README.md` | 对账 | 同级 |
| orchestrator | `../orchestrator/README.md` | 日更 | `execution_pending_resume` 先于 `execution_paper` |
| frontend/trade | `../../frontend/trade/README.md` | 交易 UI | 下游 |

## 边界
- 做：门禁（approved + risk_decision + kill off）→ 意图 → **适配器**成交/拒单 → 事件；残差 pending；续撮；成功后 portfolio→executed（仅 portfolio 类）。
- 不做：直接改现金/持仓（属 ledger）；**真实券商 SDK / 密钥 / 网络下单**（`broker_stub` / `live_gated` 仅为骨架，一律拒单）。

## 适配器（阶段 20–21）

| kind | 成交 | 说明 |
| --- | --- | --- |
| `paper` | 是 | 默认；即时撮合（含冲击成本版本） |
| `broker_stub` | **永不** | dry-run 拒单 `dry_run_no_live`；无网络/无密钥 |
| `live_gated` | **永不** | 须 `ASHARE_ALLOW_LIVE=1`；武装后仍无 SDK → `live_sdk_not_configured` |

参数表：`execution_adapter_params`（迁移 `037`/`038`）。`allow_fills=0` 时即使适配器误返回 fill 也会被服务层清空。`require_live_env=1` 且未武装 → 服务层直接 `invalid`。schedule 默认仍走 `paper`。

```bash
python main.py execution adapters
python main.py execution run --portfolio pf_xxx --adapter paper
python main.py execution run --portfolio pf_xxx --adapter broker_stub   # 仅测拒单路径
python main.py execution run --portfolio pf_xxx --adapter live_gated    # 测环境闸门
```

## 纸面口径
- 读 **本策略 sleeve** 做差额 BUY/SELL
- 现金账户级；先卖后买；`insufficient_cash` / `clamped_cash`
- SELL：T+1 lot + `can_sell`
- 成交价优先未复权 `close`
- **冲击（18b）**：与回测共用 `cost_params`；`v2_sqrt_impact` 启用 `slip + coef*sqrt(名义/ADV)`；审核/续撮时点时补 ADV；`slippage_cost` 含冲击差额
- **残差（阶段 17）**：REJECTED / 未成交部分写入 `execution_pending`；新调仓执行前 supersede 同 sleeve 旧 open，再写入本轮残差
- **续撮**：`resume-pending` 按 sleeve 用当日行情/可卖/现金再试；同日同 sleeve 幂等；`run_kind=pending_resume`
- CLI：committed 且 `fill_count>0` 立即 ledger post；已有 posting 禁止 `--force`

## 运行

```bash
cd backend
python main.py execution run --portfolio pf_xxx
python main.py execution run --approved --as-of 2026-07-23
python main.py execution resume-pending --as-of 2026-07-24 --account paper_default
python main.py execution list-pending --account paper_default
python main.py execution list
python -m execution.selfcheck
```

## 不变量
- 差额/残差只对本 `strategy_version` sleeve
- portfolio 执行前检查 approved + risk_decision + kill
- 只写事件；过账由 ledger（CLI 串联）
- pending 不入账本；续撮只产生 fill_event 后再过账
