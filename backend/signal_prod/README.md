# signal_prod

## 名称
生产信号：仅运行 `strategy_registry` 中已晋升（PAPER/LIVE）版本，写入带版本的目标权重。

## 生产数据与落库表

| 生产数据 | 落库表 | 写入时机/说明 |
| --- | --- | --- |
| 信号批次 | `signal_batch` | `signal run` 每次一档 |
| 目标权重 | `signal_prod_weight` | 调仓日 top-N 等权；幂等 UPSERT |


## 本目录模块一览
无子模块；本目录即单一业务模块实现。

## 协作模块索引（供 AI Agent）

| 模块 | README | 主要作用 | 与本模块关系 |
| --- | --- | --- | --- |
| backend（父） | `../README.md` | 总览 | 父目录 |
| database | `../../database/README.md` | 生产信号表 | 上游契约 |
| strategy_registry | `../strategy_registry/README.md` | 版本与晋升 | 上游（唯一允许运行的定义） |
| data_quality | `../data_quality/README.md` | DQ | 上游门禁（覆盖区间 passed） |
| security_master | `../security_master/README.md` | Universe | 绑定快照 |
| research_lab | `../research_lab/README.md` | 因子值 | 经库读 `research_factor_value`（非 import） |
| portfolio_construct | `../portfolio_construct/README.md` | 组合草稿 | 下游（读权重） |
| backtest | `../backtest/README.md` | 回测 | 可对生产版本做回归 |
| orchestrator | `../orchestrator/README.md` | 日更 | `schedule` 末尾跑 LIVE；其前已 `factor_refresh` |

## 边界
- 做：按 `strategy_version` 生成生产权重并落库。
- 不做：运行 DRAFT/BACKTESTED；改账本/下单；import research_lab/backtest 内部实现。

## 输入
- PAPER/LIVE 的 `strategy_version`
- 覆盖请求区间的 CORE `dq_gate=passed`
- `universe_snapshot` + `research_factor_value` + `processed_equity_bar_1d`

## 输出
- `signal_batch` / `signal_prod_weight`（含 `strategy_version` / `signal_batch_id`）

## 运行

```bash
cd backend
# 指定版本（区间）
python main.py signal run --version sv_xxx --start 2026-06-01 --end 2026-07-23
# 日更：全部 LIVE（非调仓日 → skipped）
python main.py signal run --live --as-of 2026-07-23
python main.py signal list --version sv_xxx
python -m signal_prod.selfcheck
```

口径（FACTOR_TOP_N）：调仓日用**前一交易日**因子取 top N 等权（与 `backtest` 一致，禁止前视）。

## 不变量
- 每条生产信号可追溯到 registry 版本与 Universe 快照
- 禁止读取未晋升研究路径作为实盘输入（只读已落库因子表 + registry 状态）
- DQ 未覆盖区间不得写生产信号（可用 `--no-dq-check` 仅调试）
