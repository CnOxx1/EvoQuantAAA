# risk_engine

## 名称
风险引擎：事前限额、合规校验、Kill Switch；对 execution 拥有硬否决权。

## 生产数据与落库表

| 生产数据 | 落库表 | 写入时机/说明 |
| --- | --- | --- |
| 风控决策 | `risk_decision` | 对 portfolio 做放行/否决时 |
| Kill Switch 状态 | `kill_switch` | 开/关停机时 |


## 本目录模块一览
无子模块；本目录即单一模块实现。

## 协作模块索引（供 AI Agent）

| 模块 | README | 主要作用 | 与本模块关系 |
| --- | --- | --- | --- |
| backend（父） | `../README.md` | 总览 | 父目录 |
| database | `../../database/README.md` | 风控/开关表 | 上游契约 |
| portfolio_construct | `../portfolio_construct/README.md` | 目标持仓草稿 | 上游 |
| security_master | `../security_master/README.md` | 标的合法性 | 协作 |
| ledger | `../ledger/README.md` | 持仓资金 | 读风险暴露 |
| execution | `../execution/README.md` | OMS | 下游（被否决则不可执行） |
| ops_monitor | `../ops_monitor/README.md` | 告警 | 同级 |
| api_gateway | `../api_gateway/README.md` | 人工 Kill Switch | 入口 |

## 边界
- 做：校验草稿、写风控快照、标记 `approved`/`rejected`、维护 kill switch。
- 不做：组合优化；柜台下单；在无审计情况下改限额。

## 输入
- `portfolio_id` 草稿、限额配置、账本暴露、kill switch 状态

## 输出
- 风控快照；可执行目标持仓状态；全局/账户停机开关

## 运行
- 组合后强制关卡；下单前 execution 必读开关

## 不变量
- kill switch=on 或未 approved → execution 禁止新开仓
- 否决原因落库可审计
