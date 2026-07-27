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

1. `daily`（CORE 行情→process→**tech_indicator 短窗**→CORE DQ）— **失败则中止本轮**；指标只算本轮 `universe`（默认 TOP100），永不 ALL_LISTED
2. `security_master --p0`（TOP100 / SECTOR_LEADERS 日快照）
3. ALPHA：`news_official` / `news_policy` / `valuation` / **`stock_flow`（分块）**
4. `data_quality --scope ALPHA`（仅报告，不写 gate）
5. **`signal run --live --as-of`**（无 LIVE 或非调仓日 → skipped；失败不阻断 CORE）
6. **`portfolio build --live --as-of`**（账本 NAV；同日幂等 skipped）
7. **`risk review --drafts --as-of`**（硬规则放行/否决；kill on 必拒）
8. **`execution run --approved --as-of`**（账本差额成交；无 approved → skipped）
9. **`ledger post --unposted`**（原子过账；幂等 skipped）
10. `ops_monitor.notify` 汇总本轮 failed 并落 `ops_alert`

说明：`stock_flow` 供 `FLOW_NET_5` 研究保鲜；ALPHA 失败不阻断 CORE。交易步骤（signal→ledger）失败时整轮 `status=degraded`（CORE 仍 ok）。分钟 K 不进 schedule。

## 运行

```bash
cd backend
python main.py migrate
# 非开市日快速跳过 exit 0（开发机冒烟优先用周末 as-of，避免误触 TOP100 日更）
python main.py schedule --once --as-of 2026-07-26
# 开市日完整一轮（会拉当日 CORE/ALPHA）
python main.py schedule --once
# 强制（调试）
python main.py schedule --once --force --as-of 2026-07-25
# 进程内定时（stdlib）
python main.py schedule --at 18:30 --universe TOP100
```

## 边界
- 做：顺序触发；记录步骤状态；CORE 失败中止；ALPHA 失败继续；交易步骤失败 → `degraded`。
- 不做：Airflow；业务计算；替代各模块 CLI。

## 不变量
- 跨模块只传 `job_id` 与标量参数
- CORE 先于 ALPHA
