# EvoQuantAAA Console (F1 SPA)

React 19 + Vite + TypeScript 运维控制台。只经 `api_gateway`，不直连库。

## 运行

```bash
# 终端 1：网关
cd backend
python main.py gateway --port 8080

# 终端 2：前端
cd frontend/app
npm install
npm run dev
# http://127.0.0.1:5173
```

若本机无系统 Node，可用仓库内便携 Node（勿提交）：

```powershell
$env:PATH = "$PWD\..\..\.tools\node;$env:PATH"   # 若已放到 frontend/.tools/node
# 或
$env:PATH = "C:\Users\guocongli\Desktop\jy\大a\frontend\.tools\node;$env:PATH"
npm install
npm run dev
```

构建：

```bash
npm run build
npm run preview
```

## F1–F2 范围（当前）

| 路由 | 中文 | 数据来源 |
| --- | --- | --- |
| `/` | 总览 | 策略/组合/告警/执行/残差/账本拼装 |
| `/strategies` | 策略 | `/v1/strategies` + 晋升 |
| `/portfolio` | 组合 | `/v1/portfolios` + 审核 |
| `/risk` | 风控 | Kill + decisions |
| `/research` | 研究 | `/v1/research/runs` |
| `/trade` | 交易 | `/v1/executions` + pending + 成交明细 |
| `/ledger` | 账本 | `/v1/ledger/accounts/{id}` |
| `/ops` | 运维 | `/v1/ops/alerts` |
| `/settings` | 设置 | 本机 localStorage |

## 设计

见 [`../FRONTEND_DESIGN.md`](../FRONTEND_DESIGN.md)。效果图：[`../design-mocks/`](../design-mocks/)。

遗留静态台：[`../console/`](../console/)（F0，并行保留）。
