# research

## 名称
研究实验可视化；触发实验任务与查看晋升状态。

## 生产数据与落库表

| 生产数据 | 落库表 | 写入时机/说明 |
| --- | --- | --- |
| 无 | — | 只调 API；研究数据由 backend 落库 |


## 本目录模块一览
无子模块；本目录即单一 UI 模块实现。

## 协作模块索引（供 AI Agent）

| 模块 | README | 主要作用 | 与本模块关系 |
| --- | --- | --- | --- |
| frontend（父） | `../README.md` | 总览 | 父目录 |
| api_gateway | `../../backend/api_gateway/README.md` | API | 上游 |
| research_lab | `../../backend/research_lab/README.md` | 实验计算 | 上游领域 |
| strategy_registry | `../../backend/strategy_registry/README.md` | 晋升 | 上游领域 |
| signal_prod | `../../backend/signal_prod/README.md` | 生产信号 | 只读对照 |
| backtest_view | `../backtest_view/README.md` | 回测页 | 同级 |

## 边界
- 做：浏览实验、申请晋升、查看版本状态。
- 不做：浏览器内算因子；把实验结果当 live 下单。

## 输入
- gateway：`run_id` / `strategy_version` / `batch_id`

## 输出
- 研究视图；任务/晋升请求

## 运行
- 随 frontend 启动（待定）

## 不变量
- 数据均来自 API
