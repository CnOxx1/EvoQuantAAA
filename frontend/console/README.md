# console

## 名称
运维控制台：经 `api_gateway` 查询策略 / Kill / 组合 / 账本 / 告警，并支持 Kill、晋升、风控审核写操作。

## 生产数据与落库表

| 生产数据 | 落库表 | 写入时机/说明 |
| --- | --- | --- |
| 无（本目录） | — | 只调 API；写操作由 gateway 审计入 `api_audit_log` |

## 本目录模块一览

| 文件 | 作用 |
| --- | --- |
| `index.html` | 单页壳 + 写操作表单 |
| `styles.css` | 视觉 |
| `app.js` | GET 刷新 + POST Kill / promote / review |

## 协作模块索引（供 AI Agent）

| 模块 | README | 主要作用 | 与本模块关系 |
| --- | --- | --- | --- |
| frontend（父） | `../README.md` | 前端总览 | 父目录 |
| api_gateway | `../../backend/api_gateway/README.md` | API | 上游（需 CORS） |

## 边界
- 做：概览刷新；Kill Switch 开/关；策略晋升（质量门默认开启，跳过须原因）；单组合或批量 draft 风控审核。
- 不做：直连 DB；实现撮合/因子；在 UI 暴露绕过 gateway 的内部调用。

> **注意**：推荐使用 F1 SPA [`../app/`](../app/)（`npm run dev` → http://127.0.0.1:5173）。本目录静态页为 F0 并行保留。

## 写操作（POST）

| UI | API |
| --- | --- |
| Kill 开/关 | `POST /v1/risk/kill` `{scope, is_on, reason?}` |
| 策略晋升 | `POST /v1/strategies/{version}/promote` `{to, backtest_run?, reason?, skip_gates?}` |
| 风控审核 | `POST /v1/risk/review` `{portfolio_id?}` 或 `{drafts, as_of, force?}` |

Bearer Token 与只读请求相同（填 `ASHARE_API_TOKEN` 时必填）。写结果展示在「写操作结果」面板；失败时展示 gateway `detail`（含质量门 `meta.failing`）。

## 运行

```bash
# 终端 1
cd backend && python main.py gateway --port 8080
# 终端 2
cd frontend/console && python -m http.server 8081
# 浏览器
# http://127.0.0.1:8081
```

## 不变量
- 业务真相以 API/库为准；写操作须经 gateway 审计
- 跳过质量门必须填写原因（与 CLI `--skip-gates` 一致）
