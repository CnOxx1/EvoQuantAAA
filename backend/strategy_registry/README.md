# strategy_registry

## 名称
策略/因子注册表：代码/参数版本、依赖数据版本、晋升状态（DRAFT→BACKTESTED→PAPER→LIVE→RETIRED）与**晋升质量门**。

## 生产数据与落库表

| 生产数据 | 落库表 | 写入时机/说明 |
| --- | --- | --- |
| 策略版本与参数 | `strategy_version` | `strategy register` / `promote` / `retire` |
| 状态变更审计 | `strategy_transition` | 每次登记与晋升追加一行 |
| 质量门参数 | `promotion_gate_params` | 迁移种子 `v1_default`；可用 `ASHARE_PROMOTION_GATE_VERSION` 切换 |
| 质量门评估 | `promotion_gate_result` | 每次晋升至 BACKTESTED/PAPER/LIVE 落库（含 skip） |


## 本目录模块一览
无子模块；本目录即单一业务模块实现。核心文件：`gates.py`（纯评估）、`service.py`（晋升拦截）、`transitions.py`。

## 协作模块索引（供 AI Agent）

| 模块 | README | 主要作用 | 与本模块关系 |
| --- | --- | --- | --- |
| backend（父） | `../README.md` | 总览 | 父目录 |
| database | `../../database/README.md` | 注册表契约 | 上游契约 |
| research_lab | `../research_lab/README.md` | 实验 | 上游；LIVE 门读 `research_run.meta_json.report` IC |
| backtest | `../backtest/README.md` | 回测 | 门读 `backtest_run` 收益/回撤/样本窗 |
| signal_prod | `../signal_prod/README.md` | 生产信号 | 下游；仅 PAPER/LIVE |
| risk_engine | `../risk_engine/README.md` | 风控 | 执行侧硬规则（与晋升门互补） |
| api_gateway | `../api_gateway/README.md` | API | 晋升入口（HTTP `/v1/strategies/.../promote`） |

## 边界
- 做：登记版本、参数哈希、状态机、审计轨迹、**晋升质量门**、查询当前 LIVE。
- 不做：计算因子；生成信号权重；下单；改写回测引擎指标。

## 输入
- 策略代码 / kind / 参数（FACTOR_TOP_N: factor_code, top_n, rebalance_days, universe）
- 可选 `research_run_id` / `backtest_run_id`
- 晋升动作与原因；可选 `--skip-gates` / `--gate-version`

## 输出
- `strategy_version` + `strategy_transition` + `promotion_gate_result`
- 可供 signal_prod 查询的 PAPER/LIVE 版本

## 质量门（阶段 16）

晋升至 **BACKTESTED / PAPER / LIVE** 时强制评估（`RETIRED`、降级 `LIVE→PAPER` 不评估）。默认版本 `v1_default`：

| 目标 | 要点 |
| --- | --- |
| BACKTESTED | 有 committed 回测；DD/收益/样本窗宽松 |
| PAPER | 同上，略严；不强制 IC |
| LIVE | 样本窗 ≥20 日历日；`max_drawdown≤0.40`；**必须**关联 committed `research_run` 且含 IC 报告（`ic_mean`/`ic_days`） |

指标来源：`backtest_run`（`max_drawdown` 为非负回撤幅度）；IC 来自 `research_run.meta_json.report`。  
未通过则 **拒绝晋升**，结果仍写入 `promotion_gate_result`（`passed=0`）。  
应急：`--skip-gates` **必须**带 `--reason`（审计 `skipped=1`）。

## 运行

```bash
cd backend
python main.py migrate
python main.py strategy register --code FTN_MOM20 --kind FACTOR_TOP_N \
  --factor MOM_20 --top-n 20 --rebalance-days 20 --universe TOP100 \
  --research-run rr_xxx
python main.py strategy promote --version sv_xxx --to BACKTESTED --backtest-run bt_xxx
python main.py strategy promote --version sv_xxx --to PAPER
python main.py strategy promote --version sv_xxx --to LIVE
# 应急（勿常用）
python main.py strategy promote --version sv_xxx --to LIVE --skip-gates --reason "hotfix"
python main.py strategy show --version sv_xxx
python -m strategy_registry.selfcheck
```

状态机：`DRAFT → BACKTESTED → PAPER → LIVE`；任意非终态 → `RETIRED`；`LIVE → PAPER` 可降级。
同一 `strategy_code` 至多一个 LIVE（晋升时默认自动停用旧 LIVE）。
晋升 `UPDATE` 带 `AND status=from`（CAS），并发冲突返回 failed。

## 不变量
- 无 registry 版本则不得标为 live 生产信号
- 状态变更可审计（`strategy_transition`）
- 生产向晋升（含 BACKTESTED）须过质量门或显式 skip 审计
- 模块间不 import 业务内部实现；经库交接
