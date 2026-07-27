# orchestrator

## 名称
流水线编排：日更任务序列；只传 `job_id` / batch 引用，不搬运业务载荷。

## 生产数据与落库表

| 生产数据 | 落库表 | 写入时机/说明 |
| --- | --- | --- |
| （间接）失败告警 | `ops_alert` | 每轮末尾经 `ops_monitor.notify` |
| 各模块 batch / dq_run | 既有表 | 子任务写入；本模块只传 `job_id` |

迁移：`019_ops_schedule.sql`（`ops_alert`）。

## 任务序列（`schedule`）

1. `daily`（CORE）— **失败则中止本轮**
2. `security_master --p0` — **失败则跳过全部交易步** → `degraded`
3. ALPHA：`news_official` / `news_policy` / `valuation` / `stock_flow`
4. `data_quality --scope ALPHA`
5. **`factor_refresh`** — LIVE 因子日刷；**失败跳过交易链**
6. **`signal run --live`** — **failed** 则跳过 portfolio/risk/execution_paper，但仍跑 pending 续撮 + ledger；skipped（非调仓）继续
7. **`portfolio build --live`** — 非调仓日 hold skipped
8. **`risk review --drafts`**
9. **`execution resume-pending`** — 先续撮历史残差（hold 日也需要）
10. **`execution run --approved`** — 新调仓；每单 CLI 内立即过账
11. **`ledger post --unposted`** — 兜底
12. `ops_monitor.notify`

## 边界
- 做：顺序触发；CORE/`security_master`/`factor_refresh`/`signal` 失败门禁；交易失败 → `degraded`。
- 不做：Airflow；业务计算。

## 不变量
- 跨模块只传 `job_id` 与标量参数
- CORE 先于 ALPHA
- LIVE 信号前必须刷新当日因子
