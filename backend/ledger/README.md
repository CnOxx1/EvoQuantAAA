# ledger

## 名称
资金持仓账本：消费成交事件过账；维护现金、持仓、T+1 可卖批次。

## 生产数据与落库表

| 生产数据 | 落库表 | 写入时机/说明 |
| --- | --- | --- |
| 账户 | `ledger_account` | `ledger ensure` / 迁移种子 `paper_default` |
| 过账批次 | `ledger_posting` | `ledger post`；同 execution 至多一 committed |
| 分录 | `ledger_entry` | 过账时追加（CASH_IN/OUT、POSITION_IN/OUT） |
| 余额 | `ledger_balance` | 现金与持仓数量 |
| 买入批次 | `ledger_lot` | T+1 可卖；FIFO 扣减 |


## 本目录模块一览
无子模块；本目录即单一业务模块实现。

## 协作模块索引（供 AI Agent）

| 模块 | README | 主要作用 | 与本模块关系 |
| --- | --- | --- | --- |
| backend（父） | `../README.md` | 总览 | 父目录 |
| database | `../../database/README.md` | 账本契约 | 上游契约 |
| execution | `../execution/README.md` | 订单成交事件 | 上游（只读 `fill_event`） |
| portfolio_construct | `../portfolio_construct/README.md` | 组合 | 可经库读权益（后续） |
| risk_engine | `../risk_engine/README.md` | 风控 | 可经库读暴露（后续） |
| ops_monitor | `../ops_monitor/README.md` | 对账 | 同级 |
| orchestrator | `../orchestrator/README.md` | 日更 | `schedule` 过账 unposted |
| frontend/trade | `../../frontend/trade/README.md` | UI | 经 gateway 展示 |

## 边界
- 做：`fill_event` → 分录 → 余额/批次；T+1 可卖查询；先卖后买排序过账。
- 不做：向柜台发单；无冲正情况下强制重过账；import execution 内部实现。

## 输入
- `execution_run.status=committed` + `fill_event`
- `ledger_account`（期初现金）

## 输出
- `ledger_posting` / `ledger_entry` / `ledger_balance` / `ledger_lot`

## T+1 口径
- 买入当日：`buy_date = trade_date`，当日不可卖（`sellable` 仅计 `buy_date < as_of`）
- 卖出：FIFO 扣减可卖批次；不足则过账失败

## 运行

```bash
cd backend
python main.py ledger ensure --account paper_default --opening-cash 1000000
python main.py ledger post --execution ex_xxx
python main.py ledger post --unposted --account paper_default
python main.py ledger show --account paper_default --as-of 2026-07-24
python main.py ledger sellable --account paper_default --as-of 2026-07-24
python -m ledger.selfcheck
```

## 不变量
- 余额仅由分录/过账更新
- T+1：当日买入不可卖
- 同一 `execution_id` 幂等（已 committed 则 skipped）
- 分录写入与 `posting.status=committed` **同事务**；空 `running` 可清后重试，已有分录的半完成需人工处理
- 模块间经库交接
