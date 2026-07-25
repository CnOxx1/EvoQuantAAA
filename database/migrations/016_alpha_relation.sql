-- 个股关系边（图谱原料，ALPHA）

CREATE TABLE IF NOT EXISTS raw_stock_relation (
    id                  BIGSERIAL PRIMARY KEY,
    batch_id            TEXT NOT NULL,
    src_symbol          TEXT NOT NULL,
    dst_symbol         TEXT NOT NULL,
    relation_type       TEXT NOT NULL,
    as_of_date          TEXT NOT NULL,
    weight              DOUBLE PRECISION,
    board_name          TEXT,
    holder_name         TEXT,
    holder_type         TEXT,
    coop_holder_name    TEXT,
    extra_json          TEXT,
    source_event_id     TEXT NOT NULL,
    source              TEXT NOT NULL,
    ingested_at         TEXT NOT NULL,
    UNIQUE (src_symbol, dst_symbol, relation_type, as_of_date, source_event_id, source)
);

CREATE INDEX IF NOT EXISTS idx_raw_stock_relation_asof_type
    ON raw_stock_relation (as_of_date, relation_type);
CREATE INDEX IF NOT EXISTS idx_raw_stock_relation_src
    ON raw_stock_relation (src_symbol, as_of_date);
CREATE INDEX IF NOT EXISTS idx_raw_stock_relation_dst
    ON raw_stock_relation (dst_symbol, as_of_date);
