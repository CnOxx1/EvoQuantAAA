# EvoQuantAAA 前端（Arco Design）

> 方案 **B**：React 19 + Vite + **Arco Design** + TanStack Query + React Router + `lightweight-charts`  
> 只经 `api_gateway`；默认 API `http://127.0.0.1:8088`（避免本机 8080 被代理占用）

## 启动

```powershell
# 可选：仓库内便携 Node
$env:PATH = "$PWD\.tools\node;$env:PATH"
cd frontend/app
npm install
npm run dev
```

浏览器：http://127.0.0.1:5173 · **设置**页填写网关地址（默认 `http://127.0.0.1:8088`）。

配套网关：

```powershell
cd backend
python main.py gateway --host 127.0.0.1 --port 8088
```

## 路由

| 路径 | 页 |
| --- | --- |
| `/` | 总览（管道真状态 + 纸面流水线） |
| `/market` | 市场情报（K 线 / 指标 / 上下文） |
| `/strategies` | 策略详情抽屉（transitions·质量门）+ 晋升 |
| `/portfolio` | 组合过滤 + 持仓 + 送审 |
| `/risk` | Kill + 决策 breaches 详情 |
| `/research` | 研究 run 详情（meta/freezes） |
| `/trade` | 执行详情 + 残差续撮 + 过账 |
| `/ledger` `/ops` | 账本 / 告警 |
| `/settings` | API / token / as_of / 环境 |

## 市场情报（`/market`）

| 区域 | 内容 |
| --- | --- |
| 左表 | 榜单 / 异动 / 新闻 / 龙虎榜 |
| 右上图 | 前复权日 K + 主图/副图指标 |
| 指标 | 预设 + 全量选择器（`/v1/market/indicators/meta`） |
| 右下 | 行情 / 指标末值 / 异动·龙虎·新闻 |

组件：`ChartPanel` · `IndicatorPicker` · `SymbolContext` · `PaperPipeline`。

## 纸面流水线

总览按步：`signal` → `build` → `review drafts` → `exec approved`（仅 paper）。  
`env=live` 锁定写操作。Trade 页提供续撮与 ledger post。

## 脚本

```powershell
cd frontend/app
npm run typecheck
npm run build
```

## 不变量

- 不直连数据库；唯一入口 `api_gateway`
- live 环境 UI 默认锁定写操作
- 静态 `frontend/console` 已移除
