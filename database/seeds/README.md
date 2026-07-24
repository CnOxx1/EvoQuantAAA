# seeds

## 名称
开发/测试幂等种子（日历、样例 cost_params、演示证券等）。

## 生产数据与落库表

| 生产数据 | 落库表 | 写入时机/说明 |
| --- | --- | --- |
| 开发/测试种子行 | 目标维表（如日历样例、`cost_params`） | 仅 dev/test 执行 seed；非生产主路径 |


## 本目录模块一览
无子模块；存放 seed 脚本。

## 协作模块索引（供 AI Agent）

| 模块 | README | 主要作用 | 与本模块关系 |
| --- | --- | --- | --- |
| database（父） | `../README.md` | 总览 | 父目录 |
| migrations | `../migrations/README.md` | 表结构 | 上游 |
| schema | `../schema/README.md` | 契约 | 同级 |
| data_ingest | `../../backend/data_ingest/README.md` | 生产获取 | 职责分离：seed≠生产主路径 |
| security_master | `../../backend/security_master/README.md` | 主数据 | 可提供最小证券样例 |

## 边界
- 做：最小参考数据，便于模块契约测试。
- 不做：全市场历史行情；生产唯一数据源。

## 输入
- 静态/低频维表

## 输出
- 幂等 seed 脚本

## 运行
- 默认仅 dev/test

## 不变量
- 幂等；不与生产 ingest 职责混淆
