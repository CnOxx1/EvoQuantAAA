# data_quality

## 名称
数据质量门禁：CORE 规则写 `dq_gate`；ALPHA 轻量规则仅出报告（不进 gate）。

## 生产数据与落库表

| 生产数据 | 落库表 | 写入时机/说明 |
| --- | --- | --- |
| DQ 运行 | `dq_run` | 每次检查一条 |
| 规则结果 | `dq_result` | `(dq_run_id, rule_code)` 幂等 |
| 区间闸门 | `dq_gate` | **仅 CORE** `(scope, start, end, factor_type)` |

## CORE 规则

| rule_code | severity | 含义 |
| --- | --- | --- |
| `equity_nonempty` … `calendar_align` | error/warn | 见既有 9 条 |
| `corp_action_adj_check` | warn | 除权日 close vs 理论除权价偏差 ≤ 2%；缺数 skip |

闸门：任一 **error** fail → `failed`；warn 不影响 pass。

## ALPHA 规则（不写 gate）

| rule_code | 含义 |
| --- | --- |
| `valuation_pe_null_rate` / `valuation_dup_symbol_date` | 估值空值率 / 键重复 |
| `flow_net_null_rate` / `flow_dup_keys` | 资金流空值率 / 键重复 |
| `news_publish_before_ingest` / `news_dup_title_day` | 点时≤入库；标题日重复 |

## 运行

```bash
cd backend
python main.py data_quality --scope CORE --start 2026-07-01 --end 2026-07-23 --symbol 600000
python main.py data_quality --scope ALPHA --start 2026-07-01 --end 2026-07-23
python -m data_quality.selfcheck
```

## 不变量
- CORE gate 未 pass 不得宣称区间可研究/回测
- ALPHA 失败不得阻塞 CORE
