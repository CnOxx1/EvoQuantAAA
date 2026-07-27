# strategy_registry

## 名称
策略/因子注册表：代码/参数版本、依赖数据版本、晋升状态（DRAFT→BACKTESTED→PAPER→LIVE→RETIRED）。

## 生产数据与落库表

| 生产数据 | 落库表 | 写入时机/说明 |
| --- | --- | --- |
| 策略版本与参数 | `strategy_version` | `strategy register` / `promote` / `retire` |
| 状态变更审计 | `strategy_transition` | 每次登记与晋升追加一行 |


## 本目录模块一览
无子模块；本目录即单一业务模块实现。

## 协作模块索引（供 AI Agent）

| 模块 | README | 主要作用 | 与本模块关系 |
| --- | --- | --- | --- |
| backend（父） | `../README.md` | 总览 | 父目录 |
| database | `../../database/README.md` | 注册表契约 | 上游契约 |
| research_lab | `../research_lab/README.md` | 实验 | 上游（可选 research_run） |
| backtest | `../backtest/README.md` | 回测 | 晋升 BACKTESTED 需 committed run |
| signal_prod | `../signal_prod/README.md` | 生产信号 | 下游；仅 PAPER/LIVE |
| risk_engine | `../risk_engine/README.md` | 风控 | 可约束可晋升条件（待接） |
| api_gateway | `../api_gateway/README.md` | API | 晋升入口（HTTP `/v1/strategies/.../promote`） |

## 边界
- 做：登记版本、参数哈希、状态机、审计轨迹；查询当前 LIVE。
- 不做：计算因子；生成信号权重；下单。

## 输入
- 策略代码 / kind / 参数（FACTOR_TOP_N: factor_code, top_n, rebalance_days, universe）
- 可选 `research_run_id` / `backtest_run_id`
- 晋升动作与原因

## 输出
- `strategy_version` + `strategy_transition`
- 可供 signal_prod 查询的 PAPER/LIVE 版本

## 运行

```bash
cd backend
python main.py strategy register --code FTN_MOM20 --kind FACTOR_TOP_N \
  --factor MOM_20 --top-n 20 --rebalance-days 20 --universe TOP100
python main.py strategy promote --version sv_xxx --to BACKTESTED --backtest-run bt_xxx
python main.py strategy promote --version sv_xxx --to PAPER
python main.py strategy promote --version sv_xxx --to LIVE
python main.py strategy list --status LIVE
python main.py strategy show --version sv_xxx
python -m strategy_registry.selfcheck
```

状态机：`DRAFT → BACKTESTED → PAPER → LIVE`；任意非终态 → `RETIRED`；`LIVE → PAPER` 可降级。
同一 `strategy_code` 至多一个 LIVE（晋升时默认自动停用旧 LIVE）。
晋升 `UPDATE` 带 `AND status=from`（CAS），并发冲突返回 failed。

## 不变量
- 无 registry 版本则不得标为 live 生产信号
- 状态变更可审计（`strategy_transition`）
- 模块间不 import 业务内部实现；经库交接
