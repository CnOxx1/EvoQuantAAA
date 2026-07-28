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

## F1 范围

| 路由 | 状态 |
| --- | --- |
| `/` Overview | 管道灯带（拼装现有 API） |
| `/strategies` | 状态机 + 晋升 |
| `/portfolio` | 列表 / 持仓 / 风控审核 |
| `/risk` | Kill + decisions |
| `/settings` | API base / token / env |
| Research / Trade / Ledger / Ops | F2 占位 |

## 设计

见 [`../FRONTEND_DESIGN.md`](../FRONTEND_DESIGN.md)。效果图：[`../design-mocks/`](../design-mocks/)。

遗留静态台：[`../console/`](../console/)（F0，并行保留）。
