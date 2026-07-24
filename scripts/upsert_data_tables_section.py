# -*- coding: utf-8 -*-
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SECTION_TITLE = "## 生产数据与落库表"

CONTENT: dict[str, str] = {
    "README.md": """
本仓库各业务模块的落库细节见各目录 README 本节；权威表清单见 `database/schema/README.md`。

| 层级 | 典型落库 |
| --- | --- |
| database/ | 定义表结构（migrations/schema），不产生业务行数据 |
| backend/ | 各模块写入约定 `raw_*` / oltp 表（见子目录） |
| frontend/ | **不直连库**，无业务落库 |
""",
    "ARCHITECTURE_PRINCIPLES.md": """
所有模块 README **必须**包含本节，格式如下：

```markdown
## 生产数据与落库表

| 生产数据 | 落库表 | 写入时机/说明 |
| --- | --- | --- |
| … | `table_name` | … |
```

- 无落库的模块写明「不落库」及原因。
- 表名以 `database/schema` 产消登记为准；先改契约再改代码。
""",
    "backend/README.md": """
后端各子模块分别落库；本目录本身不写业务表。汇总见 `../database/schema/README.md`。

| 生产数据 | 落库表 | 写入时机/说明 |
| --- | --- | --- |
| （本目录无） | — | 落库由 `data_ingest/*`、`ledger` 等子模块完成 |
""",
    "backend/shared/README.md": """
| 生产数据 | 落库表 | 写入时机/说明 |
| --- | --- | --- |
| 无业务数据 | — | 仅提供 DB 连接/工具；不拥有业务表写入职责 |
""",
    "backend/api_gateway/README.md": """
| 生产数据 | 落库表 | 写入时机/说明 |
| --- | --- | --- |
| 无业务主数据 | — | 只读查询或转发命令；业务写入由领域模块落库 |
| （可选）审计日志 | `api_audit_log`（待建） | 若启用网关审计再落库 |
""",
    "backend/orchestrator/README.md": """
| 生产数据 | 落库表 | 写入时机/说明 |
| --- | --- | --- |
| 任务状态 | `job_status` | 创建/更新/完成/失败任务时 |
""",
    "backend/security_master/README.md": """
| 生产数据 | 落库表 | 写入时机/说明 |
| --- | --- | --- |
| Universe 日快照 | `universe_snapshot_*` | 盘前/日更固化可交易集合 |
| （读）上市/行业/ST/成分原料 | `raw_security_listing` 等 | 只读 `core_ref` 已提交 raw，不改 raw |
""",
    "backend/data_ingest/README.md": """
本包各子域写入对应 `raw_*` / 水位 / `ingest_batch`；明细见各子目录本节。

| 生产数据 | 落库表 | 写入时机/说明 |
| --- | --- | --- |
| 批次元数据 | `ingest_batch` | 各子域任务经 ingest_common 创建/提交 |
| CORE/ALPHA 原始数据 | 各 `raw_*` | 见 `core_ref` / `core_market` / `alpha_*` |
""",
    "backend/data_ingest/ingest_common/README.md": """
| 生产数据 | 落库表 | 写入时机/说明 |
| --- | --- | --- |
| 拉取批次 | `ingest_batch` | create → committed/failed；未 commit 不得对外就绪 |
""",
    "backend/data_ingest/core_ref/README.md": """
| 生产数据 | 落库表 | 写入时机/说明 |
| --- | --- | --- |
| 交易日历 | `raw_trade_calendar` | kind=`calendar` |
| 上市/退市原料 | `raw_security_listing` | kind=`listing` |
| 行业分类 | `raw_industry_class` | kind=`industry` |
| 股本 | `raw_share_capital` | kind=`share_capital` |
| 指数成分权重 | `raw_index_member` | kind=`index_member`（P1） |
| ST 等状态史 | `raw_special_treat` | kind=`special_treat`（P1） |
| 批次 | `ingest_batch` | 经 ingest_common |
""",
    "backend/data_ingest/core_market/README.md": """
| 生产数据 | 落库表 | 写入时机/说明 |
| --- | --- | --- |
| 股票日线 | `raw_equity_bar_1d` | kind=`equity_1d` |
| 复权因子 | `raw_adj_factor` | kind=`adj_factor` |
| 停牌 | `raw_suspend` | kind=`suspend` |
| 涨跌停 | `raw_limit_*` | kind=`limit` |
| 指数日线 | `raw_index_bar_1d` | kind=`index_1d` |
| 公司行为 | `raw_corp_action` | kind=`corp_action`（P1） |
| 分钟线 | `raw_equity_bar_1m` | kind=`equity_1m`（P2） |
| 批次 | `ingest_batch` | 经 ingest_common |
""",
    "backend/data_ingest/alpha_fundamental/README.md": """
| 生产数据 | 落库表 | 写入时机/说明 |
| --- | --- | --- |
| 财务报表原值 | `raw_fund_statement` | kind=`statement` |
| 财务指标 | `raw_fund_indicator` | kind=`indicator` |
| 一致预期 | `raw_consensus_estimate` | kind=`consensus`（P2） |
| 批次 | `ingest_batch` | 经 ingest_common |
""",
    "backend/data_ingest/alpha_flow/README.md": """
| 生产数据 | 落库表 | 写入时机/说明 |
| --- | --- | --- |
| 资金流向 | `raw_money_flow` | kind=`northbound` / `stock_flow` |
| 融资融券 | `raw_margin` | kind=`margin`（P2） |
| 龙虎榜 | `raw_dragon_tiger` | kind=`dragon_tiger`（P2） |
| 大宗交易 | `raw_block_trade` | kind=`block_trade`（P2） |
| 批次 | `ingest_batch` | 经 ingest_common |
""",
    "backend/data_ingest/alpha_announcement/README.md": """
本模块（已实现）生产法定公告/监管披露原始数据，经库交接后供 process / research / risk 消费。

| 生产数据 | 落库表 | 写入时机/说明 |
| --- | --- | --- |
| 公告元数据（标题、分类、点时、链接等） | `raw_announcement` | `ann_incremental` / `ann_watchlist` / `ann_backfill` / `ann_by_category` 拉取成功并 upsert |
| 增量/订阅水位线 | `ingest_announcement_watermark` | 仅 `ann_incremental`、`ann_watchlist` 在有更新时推进（不回退） |
| 任务批次 | `ingest_batch` | 经 `ingest_common`：created → committed/failed |

**不写入**：`raw_news_media`（媒体新闻）、财报数值表（`raw_fund_*`，归 alpha_fundamental）。

主要字段（`raw_announcement`）：`source_ann_id`, `symbol`, `title`, `publish_time`, `category_raw`, `category_norm`, `url`, `content_uri`, `content_hash`, `channel`, `source`, `batch_id`, `ingested_at`。

迁移脚本：`database/migrations/001_alpha_announcement.sql`。
""",
    "backend/data_ingest/alpha_news_monitor/README.md": """
| 生产数据 | 落库表 | 写入时机/说明 |
| --- | --- | --- |
| 媒体新闻/资讯 | `raw_news_media` | kind=`news_incremental` / `news_watchlist` / `news_backfill` |
| 新闻监控水位线 | `ingest_news_watermark` | 增量/订阅任务更新 |
| 批次 | `ingest_batch` | 经 ingest_common |

**不写入**：`raw_announcement`（法定公告归 alpha_announcement）。
""",
    "backend/data_process/README.md": """
| 生产数据 | 落库表 | 写入时机/说明 |
| --- | --- | --- |
| 清洗/复权/对齐后数据 | `processed_*` | 读取已提交 `raw_*` 加工后写入 |
""",
    "backend/data_quality/README.md": """
| 生产数据 | 落库表 | 写入时机/说明 |
| --- | --- | --- |
| DQ 门禁结果 | `dq_result` | 对指定 batch 跑规则后写入 pass/fail |
""",
    "backend/research_lab/README.md": """
| 生产数据 | 落库表 | 写入时机/说明 |
| --- | --- | --- |
| 实验因子/信号/元数据 | `research_*` | 实验任务完成时；不可直接进实盘 |
""",
    "backend/signal_prod/README.md": """
| 生产数据 | 落库表 | 写入时机/说明 |
| --- | --- | --- |
| 生产信号 | `signal_prod_*` | 仅已晋升 `strategy_version` 运行后写入 |
""",
    "backend/strategy_registry/README.md": """
| 生产数据 | 落库表 | 写入时机/说明 |
| --- | --- | --- |
| 策略/因子版本与晋升状态 | `strategy_version` | 登记、审批、晋升、停用时 |
""",
    "backend/backtest/README.md": """
| 生产数据 | 落库表 | 写入时机/说明 |
| --- | --- | --- |
| 回测报告/成交假设等 | 回测结果表（如 `backtest_report_*`，契约待建） | 回测 run 完成时 |
| （读）费用参数 | `cost_params` | 只读 |
""",
    "backend/portfolio_construct/README.md": """
| 生产数据 | 落库表 | 写入时机/说明 |
| --- | --- | --- |
| 目标持仓草稿 | `portfolio_target` | 组合构建完成；status=draft |
""",
    "backend/risk_engine/README.md": """
| 生产数据 | 落库表 | 写入时机/说明 |
| --- | --- | --- |
| 风控决策 | `risk_decision` | 对 portfolio 做放行/否决时 |
| Kill Switch 状态 | `kill_switch` | 开/关停机时 |
""",
    "backend/execution/README.md": """
| 生产数据 | 落库表 | 写入时机/说明 |
| --- | --- | --- |
| 委托/成交事件 | `order_event` / `fill_event` | 下单与回报时（不过账） |
""",
    "backend/ledger/README.md": """
| 生产数据 | 落库表 | 写入时机/说明 |
| --- | --- | --- |
| 账本分录 | `ledger_entry` | 消费成交/费用事件过账 |
| 余额/可卖 | `balance`（及可卖快照字段/表） | 过账后更新 |
""",
    "backend/ops_monitor/README.md": """
| 生产数据 | 落库表 | 写入时机/说明 |
| --- | --- | --- |
| 告警 | 告警表（如 `ops_alert`，待建） | 监控触发时 |
| 对账报告 | 对账表（如 `reconcile_report`，待建） | 对账任务完成时 |
| （读）批次/订单/账本 | `ingest_batch` 等 | 只读已落库状态 |
""",
    "frontend/README.md": """
| 生产数据 | 落库表 | 写入时机/说明 |
| --- | --- | --- |
| 无 | — | 前端**不直连数据库**；展示与操作经 api_gateway |
""",
    "frontend/console/README.md": """
| 生产数据 | 落库表 | 写入时机/说明 |
| --- | --- | --- |
| 无 | — | 只调 API 展示；不落业务库 |
""",
    "frontend/research/README.md": """
| 生产数据 | 落库表 | 写入时机/说明 |
| --- | --- | --- |
| 无 | — | 只调 API；研究数据由 backend 落库 |
""",
    "frontend/backtest_view/README.md": """
| 生产数据 | 落库表 | 写入时机/说明 |
| --- | --- | --- |
| 无 | — | 只调 API 展示回测结果 |
""",
    "frontend/portfolio/README.md": """
| 生产数据 | 落库表 | 写入时机/说明 |
| --- | --- | --- |
| 无 | — | 确认类操作经 API，由 backend 落库 |
""",
    "frontend/trade/README.md": """
| 生产数据 | 落库表 | 写入时机/说明 |
| --- | --- | --- |
| 无 | — | 下单请求经 API；订单/账本由 execution/ledger 落库 |
""",
    "frontend/ops/README.md": """
| 生产数据 | 落库表 | 写入时机/说明 |
| --- | --- | --- |
| 无 | — | 告警确认/重跑经 API，由 ops/orchestrator 落库 |
""",
    "database/README.md": """
| 生产数据 | 落库表 | 写入时机/说明 |
| --- | --- | --- |
| 不产生业务行数据 | — | 本目录定义/迁移表结构与种子；业务写入在 backend |
| 表契约说明 | （文档）`schema/` | 产消登记 |
""",
    "database/migrations/README.md": """
| 生产数据 | 落库表 | 写入时机/说明 |
| --- | --- | --- |
| 无业务行 | — | 仅执行 DDL/结构变更；例如 `001_alpha_announcement.sql` 创建 `raw_announcement` 等表 |
""",
    "database/schema/README.md": """
| 生产数据 | 落库表 | 写入时机/说明 |
| --- | --- | --- |
| 无业务行 | — | 本目录为契约文档；实际建表见 `migrations/`，写入方见下表「产消登记」 |
""",
    "database/seeds/README.md": """
| 生产数据 | 落库表 | 写入时机/说明 |
| --- | --- | --- |
| 开发/测试种子行 | 目标维表（如日历样例、`cost_params`） | 仅 dev/test 执行 seed；非生产主路径 |
""",
}


def upsert_section(text: str, body: str) -> str:
    body = body.strip("\n") + "\n"
    section = f"{SECTION_TITLE}\n\n{body}\n"
    if SECTION_TITLE in text:
        pattern = re.compile(
            rf"{re.escape(SECTION_TITLE)}\n.*?(?=\n## |\Z)",
            re.S,
        )
        return pattern.sub(section.rstrip() + "\n\n", text, count=1)

    m = re.search(r"(## 名称\n.*?\n)(?=\n## )", text, re.S)
    if m:
        return text[: m.end()] + "\n" + section + text[m.end() :]

    m3 = re.search(r"\n---\n|\n## ", text)
    if m3:
        return text[: m3.start()] + "\n" + section + text[m3.start() :]
    return text.rstrip() + "\n\n" + section


def patch_principles(text: str) -> str:
    """Ensure README template lists the new section."""
    old = """```markdown
# <目录名>

## 名称
## 本目录模块一览
## 协作模块索引（供 AI Agent）
## 边界
## 输入
## 输出
## 运行
## 不变量
```"""
    new = """```markdown
# <目录名>

## 名称
## 生产数据与落库表
## 本目录模块一览
## 协作模块索引（供 AI Agent）
## 边界
## 输入
## 输出
## 运行
## 不变量
```"""
    if old in text:
        text = text.replace(old, new)
    elif "## 生产数据与落库表" not in text.split("最小结构")[1] if "最小结构" in text else True:
        text = text.replace(
            "## 名称\n## 本目录模块一览",
            "## 名称\n## 生产数据与落库表\n## 本目录模块一览",
        )
    return text


def main() -> None:
    missing = []
    for rel, body in CONTENT.items():
        path = ROOT / rel
        if not path.exists():
            missing.append(rel)
            continue
        old = path.read_text(encoding="utf-8")
        new = upsert_section(old, body)
        if rel == "ARCHITECTURE_PRINCIPLES.md":
            new = patch_principles(new)
        path.write_text(new, encoding="utf-8", newline="\n")
        print("OK", rel)

    lack = []
    for p in ROOT.rglob("*.md"):
        if "scripts" in p.parts:
            continue
        text = p.read_text(encoding="utf-8")
        if SECTION_TITLE not in text:
            lack.append(str(p.relative_to(ROOT)))
    print("missing_files", missing)
    print("lack_section", lack)


if __name__ == "__main__":
    main()
