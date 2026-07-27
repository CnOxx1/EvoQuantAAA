# e2e

## 名称
生产链路短窗端到端回归：自备种子，不拉 ALL_LISTED / 长窗行情。

## 覆盖步骤
register（含 research_run IC）→ promote(BACKTESTED/PAPER/LIVE，过质量门) → signal → portfolio（含同日幂等）→ risk → execution（含幂等）→ ledger（含幂等）→ API TestClient

## 运行

```bash
cd backend
python main.py migrate
python main.py e2e
# 或
python -m e2e.prod_path
```

## 种子约定
- Universe `E2E_TOP10`、账户 `e2e_smoke`、策略码 `E2E_FTN`
- 信号/组合点时窗约 `2026-06-09`–`2026-06-10`；`require_dq=False`（仅回归）
- 回测窗拉长至 ≥20 日历日；`research_run.meta_json.report` 含假 IC，供 LIVE 质量门
- 每次 seed 清空 `e2e_smoke` 持仓/sleeve/lot，并重置现金，保证可重复产生 fill

## 边界
- 做：可重复冒烟，断言幂等与 API 可读、晋升门可通过
- 不做：替代 pytest 纯函数单测；全市场灌数
