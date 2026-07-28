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
| `/` | 总览（管道灯带） |
| `/market` | 市场情报（见下） |
| `/strategies` | 策略 + 晋升 |
| `/portfolio` | 组合 + 送审 |
| `/risk` | Kill + 决策 |
| `/research` `/trade` `/ledger` `/ops` | 只读列表 |
| `/settings` | API / token / as_of / 环境 |

## 市场情报（`/market`）

左右分栏工作台：

| 区域 | 内容 |
| --- | --- |
| 左表 | 榜单 / 异动 / 新闻 / 龙虎榜（分页）；点击行选中标的 |
| 右上图 | 前复权日 K（`/v1/market/bars`）；主图叠加 + 副图 |
| 指标 | 快捷预设 MA/EMA/BOLL/MACD/RSI；`+N` 打开全量选择器（`/v1/market/indicators/meta`，库内约 279 码） |
| 右下上下文 | 最新行情 OHLC·量额、已选指标末值、异动/龙虎/相关新闻 |

限额：主图最多 8 条叠加、副图最多 6 条；主图/副图由 meta 的 `placement` 自动分流。

相关组件：`ChartPanel` · `IndicatorPicker` · `SymbolContext`；文案集中在 `src/i18n/zh.ts`。

## 脚本

```powershell
cd frontend/app
npm run typecheck
npm run build
```

## 不变量

- 不直连数据库；唯一入口 `api_gateway`
- live 环境 UI 默认锁定提示
- 静态 `frontend/console` 已移除；统一使用本 SPA
