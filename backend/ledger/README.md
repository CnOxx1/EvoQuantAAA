# ledger

## 名称
账本：成交事件过账；维护现金/持仓余额与 T+1 可卖批次。

## 生产数据与落库表

| 生产数据 | 落库表 | 写入时机/说明 |
| --- | --- | --- |
| 账户 | `ledger_account` | `ledger ensure` / 首次 post 自动 |
| 过账批次 | `ledger_posting` | `ledger post`；按 execution 幂等 |
| 分录 | `ledger_entry` | 与 posting committed 同事务 |
| 余额 | `ledger_balance` | 现金（账户级）+ 合计持仓 |
| 策略持仓 | `ledger_sleeve_position` | 按 `(account, strategy_version, symbol)` |
| 买入批次 | `ledger_lot` | T+1 可卖；FIFO；含 `strategy_version` |

迁移：`027_ledger.sql` + `031_strategy_sleeve.sql`。

## 协作模块索引（供 AI Agent）

| 模块 | README | 主要作用 | 与本模块关系 |
| --- | --- | --- | --- |
| execution | `../execution/README.md` | OMS 成交事件 | 上游；CLI 每个 committed 后立即 post |
| portfolio_construct | `../portfolio_construct/README.md` | 目标持仓 | 读账户 NAV |
| risk_engine | `../risk_engine/README.md` | 风控 | 间接 |
| orchestrator | `../orchestrator/README.md` | 日更 | `ledger_post` 兜底未过账 |

## 边界
- 做：fill → 分录；更新现金/合计持仓/sleeve/lot；T+1 可卖校验。
- 不做：下单；改目标持仓；绕过 execution 直接改仓。

## 不变量
- 现金账户共享；**持仓按 strategy_version sleeve 隔离**（防多策略串仓）
- 同 execution 至多一 committed posting；不支持 `--force` 重过账（需冲正）
- SELL 仅扣本策略可卖 lot（`buy_date < as_of`）
- 恒等式（过账后应满足）：
  - `sum(ledger_sleeve_position.qty)`（同 account+symbol）= `ledger_balance` POSITION
  - `sum(ledger_lot.qty_remaining)`（同 account+strategy_version+symbol）= 对应 sleeve qty

## 历史数据（迁移 `031`）
- 存量账户级 POSITION 会回填到 `strategy_version=''` 的 sleeve/lot
- **新过账**写入真实 `strategy_version`；execution 只读命名 sleeve，不会误卖 `''` 旧仓
- 开发/冒烟账户若同时存在 `''` 与命名 sleeve，账户合计 NAV 会偏高；可清空该账户 sleeve+lot+POSITION 后重跑 e2e，或归档 `strategy_version=''` 行
- 旧 `portfolio_target_position.can_sell` 可能为 NULL；阶段 14 之后新建草稿必填 0/1
