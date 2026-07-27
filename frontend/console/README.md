# console

## 名称
总控台 / 仪表盘：经 `api_gateway` 只读展示策略、Kill、组合、账本与告警。

## 生产数据与落库表

| 生产数据 | 落库表 | 写入时机/说明 |
| --- | --- | --- |
| 无 | — | 只调 API 展示；不落业务库 |

## 本目录模块一览

| 文件 | 作用 |
| --- | --- |
| `index.html` | 单页壳 |
| `styles.css` | 视觉 |
| `app.js` | fetch `/v1/*` |

## 协作模块索引（供 AI Agent）

| 模块 | README | 主要作用 | 与本模块关系 |
| --- | --- | --- | --- |
| frontend（父） | `../README.md` | 前端总览 | 父目录 |
| api_gateway | `../../backend/api_gateway/README.md` | API | 上游（需 CORS） |

## 边界
- 做：只读概览；配置 API Base / Bearer。
- 不做：直连 DB；完整审批表单（写操作仍用 CLI /docs）。

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
- 只展示已持久化可查询状态；业务真相以 API/库为准
