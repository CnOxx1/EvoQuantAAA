# ops_monitor

## 名称
运维监控与告警；覆盖度只读查询。

## 生产数据与落库表

| 生产数据 | 落库表 | 写入时机/说明 |
| --- | --- | --- |
| 告警 | `ops_alert` | `notify_round`：汇总 ingest/process/dq failed |
| （读）覆盖度 | 各 `raw_*` | `coverage` 命令只读 |

迁移：`019_ops_schedule.sql`。

## 能力

| 入口 | 说明 |
| --- | --- |
| `notify.py::notify_round` | 汇总失败 → 写 `ops_alert` → 打印摘要；`ASHARE_ALERT_WEBHOOK` 有值则 POST JSON |
| `coverage.py` / `main.py coverage` | 核心表×月份：equity/adj/suspend/limit/index/valuation/money_flow/news/tech_1d/equity_min |

## 运行

```bash
cd backend
python main.py coverage --universe TOP100 --start 2023-01-01 --end 2026-07-23
# 告警通常由 schedule 末尾触发；也可在 Python 中调用 notify_round
```

## 边界
- 做：失败汇聚、告警落库、可选 webhook、覆盖度矩阵。
- 不做：修数；替代领域模块；无审计强改。

## 不变量
- 告警可审计（`alert_id` / `job_id` / `ref_id`）
- 不搬运业务大数据包
