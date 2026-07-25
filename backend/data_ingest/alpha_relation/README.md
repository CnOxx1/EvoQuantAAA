# alpha_relation

## 名称
量化 ALPHA · **个股关系边**获取：落库供后台关系图谱展示与研究（不阻塞 CORE）。

## 生产数据与落库表

| 生产数据 | 落库表 | 说明 |
| --- | --- | --- |
| 个股—个股关系边 | `raw_stock_relation` | 无向存储：`src_symbol < dst_symbol` |
| 批次 | `ingest_batch` | 经 ingest_common |

迁移：`016_alpha_relation.sql`。

### 边类型 `relation_type`

| 类型 | kind | 含义 | 源 |
| --- | --- | --- | --- |
| `HOT_RELATE` | `hot_relate` | 东财人气「相关股票」 | `stock_hot_rank_relate_em` |
| `HOLDER_TEAM` | `holder_team` | 股东协同共持（明细展开） | `stock_gdfx_free_holding_teamwork_em` |
| `CONCEPT_CO` / `INDUSTRY_CO` | `board_co` | 同概念/同行业成分共板 | `stock_board_*_cons_em` |

关键字段：`as_of_date`（点时日）、`weight`（强度）、`board_name` / `holder_name`（边属性）。

## 运行

```bash
cd backend
python main.py migrate

# 人气相关股（推荐图谱主路径；需标的）
python main.py alpha_relation --kind hot_relate --universe TOP100 --end 2026-07-25
python main.py alpha_relation --kind hot_relate --symbol 600519 --symbol 000858

# 股东协同共持（默认社保；可用 --universe 过滤两端都在池内的边）
python main.py alpha_relation --kind holder_team --holder-type 社保 --universe TOP100

# 同板块共现（需板块名）
python main.py alpha_relation --kind board_co --board-type CONCEPT --board-name 人工智能 --universe TOP100
python main.py alpha_relation --kind board_co --board-type INDUSTRY --board-name 白酒

python -m data_ingest.alpha_relation.selfcheck
```

### 图谱消费建议

```text
节点 = Universe 成员（security_master）
边   = raw_stock_relation 按 as_of_date + relation_type 过滤
UI   = 无向图；边宽/颜色映射 weight / relation_type
```

说明：
- `holder_type=全部` 分页极多，**开发机勿用**；用 `社保`/`基金`/`QFII` 等。
- `board_co` 单板块成分若过多，入库前截断前 40 只做完全图，避免边爆炸。
- 点时用 `as_of_date`，禁止用 `ingested_at`。

## 不变量
- 幂等：`(src, dst, relation_type, as_of_date, source_event_id, source)`
- ALPHA 失败不阻塞 CORE
