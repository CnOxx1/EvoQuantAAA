# security_master

## 名称
证券主数据与 Universe：基于已提交 `core_ref` raw，固化**点时**可交易集合快照。

## 生产数据与落库表

| 生产数据 | 落库表 | 写入时机/说明 |
| --- | --- | --- |
| Universe 头 | `universe_snapshot` | `(as_of_date, universe_code)` 幂等替换 |
| Universe 成员 | `universe_snapshot_member` | 挂 `universe_snapshot_id` |
| （读）上市/行业/ST/成分 | `raw_security_listing` 等 | 只读，不改 raw |

## universe_code（P0）

| code | 含义 |
| --- | --- |
| `ALL_LISTED` | 截至 as_of 已上市且未退市 |
| `HS300` | 上市 ∩ 沪深300 最新成分（trade_date≤as_of） |
| `HS300_EX_ST` | HS300 排除当日仍生效的 ST |

成员字段含：交易所/板块、行业、`is_st`/`treat_type`、指数权重、`is_eligible`。

## 点时规则
- 上市：`list_date <= as_of` 且（无退市或 `delist_date > as_of`）
- ST：`effective_date <= as_of` 且（无结束或 `end_date > as_of`）
- 成分：取 `trade_date <= as_of` 的最近成分日；若无则回退该指数全局最近日
- 非开市日：默认回退到上一开市日（写入 meta）

## 边界
- 做：生成 `universe_snapshot_id`；提供可交易集合快照。
- 不做：拉行情；算因子；下单；改 raw。

## 运行

```bash
cd backend
python main.py migrate
python main.py core_ref --kind special_treat --source akshare
python main.py core_ref --kind index_member --source akshare --index 000300
python main.py security_master --p0 --as-of 2026-07-23
python -m security_master.selfcheck
```

## 不变量
- 策略/组合只消费已提交快照，不临时拼名单
- 历史回测用历史 as_of 快照，禁止用最新 ST 回刷历史
