# security_master

## 名称
证券主数据与 Universe：基于已提交 `core_ref` raw，固化**点时**可交易集合快照。

## 生产数据与落库表

| 生产数据 | 落库表 | 写入时机/说明 |
| --- | --- | --- |
| Universe 头 | `universe_snapshot` | `(as_of_date, universe_code)` 幂等替换 |
| Universe 成员 | `universe_snapshot_member` | 挂 `universe_snapshot_id` |
| （读）上市/行业/ST/成分/股本 | `raw_*` | 只读，不改 raw |

## 本地沉淀策略（重要）

**不对 6000+ 全市场做行情/基本面落库。**  
默认本地只维护：

| code | 含义 | 规模 |
| --- | --- | --- |
| `TOP100` | 按股本×收盘（近似市值）或股本排序的前 100（排除 ST） | ~100 |
| `SECTOR_LEADERS` | 每个行业（默认申万一级）取 1 只龙头 | ~行业数 |

其余个股：**按需** `core_market --symbol xxx` 临时拉取，不进默认 Universe。

可选（研究用，非默认 P0）：`ALL_LISTED` / `HS300` / `HS300_EX_ST`。

`--p0` = `TOP100` → `SECTOR_LEADERS`。

排名：优先 `total_shares*close`（仅用库内已有日线，不触发全市场拉行情）；否则流通/总股本；股本缺失时用上市名单补齐。

## 点时规则
- 上市：`list_date <= as_of` 且（无退市或 `delist_date > as_of`）
- ST：`effective_date <= as_of` 且（无结束或 `end_date > as_of`）
- 成分：取 `trade_date <= as_of` 的最近成分日
- 非开市日：默认回退到上一开市日（写入 meta）

## 边界
- 做：生成 `universe_snapshot_id`；提供可交易集合快照。
- 不做：拉行情；算因子；下单；改 raw；全市场 bulk 灌数。

## 运行

```bash
cd backend
python main.py migrate
python main.py core_ref --p0 --start 2026-07-01 --end 2026-07-31 --source akshare
python main.py security_master --p0 --as-of 2026-07-23
# 只灌龙头
python main.py core_market --p0 --universe TOP100 --start 2026-07-01 --end 2026-07-23 --skip-existing --chunk-size 10
# 按需单票
python main.py core_market --kind equity_1d --start 2026-07-01 --end 2026-07-23 --symbol 600519
```

## 不变量
- 策略/组合只消费已提交快照，不临时拼名单
- 历史回测用历史 as_of 快照，禁止用最新 ST 回刷历史
- 默认 ingest Universe 为 `TOP100` / `SECTOR_LEADERS`，禁止默认 `ALL_LISTED` 行情灌数
