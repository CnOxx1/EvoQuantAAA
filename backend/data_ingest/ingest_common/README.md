# ingest_common

## 名称
ingest 基建：batch 生命周期、幂等写、`ingest_module`/`ingest_kind`、源适配。服务量化 CORE/ALPHA 各域。

## 生产数据与落库表

| 生产数据 | 落库表 | 写入时机/说明 |
| --- | --- | --- |
| 拉取批次 | `ingest_batch` | create → committed/failed；未 commit 不得对外就绪 |


## 本目录模块一览
无子模块；仅供 `data_ingest` 内引用。

## 协作模块索引（供 AI Agent）

| 模块 | README | 主要作用 | 与本模块关系 |
| --- | --- | --- | --- |
| data_ingest（父） | `../README.md` | CORE/ALPHA 总览 | 父目录 |
| core_ref / core_market / alpha_* | `../README.md` | 各域 | 消费者 |
| shared | `../../shared/README.md` | 全局工具 | 可引用 |
| database | `../../../database/README.md` | ingest_batch | 契约 |

## 边界
- 做：batch 创建/提交/失败；统一写入；限流重试；SourceAdapter。  
- 不做：字段业务映射；调度；DQ；区分「策略能不能用」（那是 DQ/process）。

## 输入 / 输出
- 入：任务参数（module/kind）、源配置  
- 出：`ingest_batch` 与工具 API

## 运行
被各域引用；无独立策略入口。

## 不变量
- 不依赖各业务域（防循环）  
- 未 commit 不得对外就绪  
- batch 元数据可区分 CORE / ALPHA，便于编排优先 CORE
