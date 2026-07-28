# risk_engine

## 名称
风险引擎：事前硬规则、Kill Switch；对 execution 拥有硬否决权。

## 生产数据与落库表

| 生产数据 | 落库表 | 写入时机/说明 |
| --- | --- | --- |
| 风控决策 | `risk_decision` | `risk review`；同步写 `portfolio_target.status` |
| Kill Switch | `kill_switch` | `risk kill --on/--off` |
| 限额参数 | `risk_limits` | 迁移种子 `v1_default` / `v2_adv_industry` |


## 本目录模块一览
无子模块；本目录即单一模块实现。

## 协作模块索引（供 AI Agent）

| 模块 | README | 主要作用 | 与本模块关系 |
| --- | --- | --- | --- |
| backend（父） | `../README.md` | 总览 | 父目录 |
| database | `../../database/README.md` | 风控/开关表 | 上游契约 |
| portfolio_construct | `../portfolio_construct/README.md` | 目标持仓草稿 | 上游 |
| security_master | `../security_master/README.md` | 标的合法性 | 协作（经库） |
| ledger | `../ledger/README.md` | 持仓资金 | 读暴露（待接） |
| execution | `../execution/README.md` | OMS | 下游（approved + kill off） |
| ops_monitor | `../ops_monitor/README.md` | 告警 | 同级 |
| orchestrator | `../orchestrator/README.md` | 日更 | `schedule` 审 draft |
| api_gateway | `../api_gateway/README.md` | 人工 Kill Switch | 入口（HTTP `/v1/risk/kill`） |

## 边界
- 做：校验 draft、写 `risk_decision`、标记 portfolio `approved`/`rejected`、维护 kill switch；同账户同日合并敞口。
- 不做：组合优化；柜台下单；在无审计情况下改限额（改 `risk_limits` 需新迁移/种子）。

## 输入
- `portfolio_id`（status=draft）、`risk_limits`、`kill_switch`
- 同账户同日其他 draft/approved/executed（合并敞口）

## 输出
- `risk_decision`；`portfolio_target.status` ∈ {approved, rejected}

## 硬规则（v1_default）
- 单票权重 / 持仓只数 / 总敞口 / Kill Switch
- 整手校验用 `cost_params.lot_size`（默认 100）
- **账户级**：同账户同日多策略目标腿按 `target_value` 合并后，相对合计 `nav` 再验单票与总敞口

## 硬规则（v2_adv_industry，阶段 18a）
在 v1 基础上启用（`risk review --limits-version v2_adv_industry`）：
- **行业集中度**：同行业 `target_value` 合计 / NAV ≤ `max_industry_weight`（默认 30%）；行业来自 universe 快照成员或 `raw_industry_class` 点时
- **ADV 参与度**：单票 `target_value` / 近 N 日均成交额（`processed_equity_bar_1d.amount`，默认 20 日）≤ `max_adv_participation`（默认 10%）
- 缺行业码 / 缺 ADV → 硬拒绝（`MISSING_INDUSTRY` / `MISSING_ADV`）
- 账户合并同验：`ACCOUNT_MAX_INDUSTRY_WEIGHT` / `ACCOUNT_MAX_ADV_PARTICIPATION`
- `v1_default` 新增列为 NULL，行为不变

| code | 含义 |
| --- | --- |
| `KILL_SWITCH_ON` | GLOBAL 或账户 Kill Switch 开启 |
| `MAX_SINGLE_WEIGHT` | 单票权重 > 15%（本策略） |
| `MAX_NAMES` / `MIN_NAMES` | 持仓只数越界 |
| `MAX_GROSS_EXPOSURE` | invested/nav > 101%（本策略） |
| `ACCOUNT_MAX_SINGLE_WEIGHT` | 账户合并单票权重超限 |
| `ACCOUNT_MAX_GROSS_EXPOSURE` | 账户合并总敞口超限 |
| `MAX_INDUSTRY_WEIGHT` | 单策略行业权重超限（v2） |
| `MAX_ADV_PARTICIPATION` | 单策略 ADV 参与度超限（v2） |
| `MISSING_INDUSTRY` / `MISSING_ADV` | v2 启用时缺数据 |
| `ACCOUNT_MAX_INDUSTRY_WEIGHT` | 账户合并行业超限（v2） |
| `ACCOUNT_MAX_ADV_PARTICIPATION` | 账户合并 ADV 超限（v2） |
| `CANNOT_BUY` | 目标股数>0 但 can_buy≠1 |
| `LOT_SIZE` | 股数非整手（按 `cost_params.lot_size`） |

## 运行

```bash
cd backend
python main.py risk review --portfolio pf_xxx
python main.py risk review --portfolio pf_xxx --limits-version v2_adv_industry
python main.py risk review --drafts --as-of 2026-07-23
python main.py risk kill --on --scope GLOBAL --reason halt
python main.py risk kill --off --scope GLOBAL
python main.py risk status
python main.py risk list --status approved
python -m risk_engine.selfcheck
```

## 不变量
- kill switch=on 或未 approved → execution 禁止新开仓
- 否决原因落库可审计（`breaches_json`）
- Kill 解除后：曾因 Kill 否决的组合可无 `--force` 重审
- 模块间不 import 业务内部实现；经库交接
