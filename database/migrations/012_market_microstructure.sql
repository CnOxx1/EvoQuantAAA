-- 盘口异动（core_market.abnormal_move）+ 龙虎榜营业部（alpha_flow.dragon_tiger_seat）

CREATE TABLE IF NOT EXISTS raw_abnormal_move (
    id              BIGSERIAL PRIMARY KEY,
    batch_id        TEXT NOT NULL,
    trade_date      TEXT NOT NULL,
    event_time      TEXT,
    symbol          TEXT NOT NULL,
    name            TEXT,
    change_type     TEXT NOT NULL,
    related_info    TEXT,
    extra_json      TEXT,
    source_event_id TEXT NOT NULL,
    source          TEXT NOT NULL,
    ingested_at     TEXT NOT NULL,
    UNIQUE (trade_date, change_type, symbol, source_event_id, source)
);

CREATE INDEX IF NOT EXISTS idx_raw_abnormal_move_date_type
    ON raw_abnormal_move (trade_date, change_type);

CREATE INDEX IF NOT EXISTS idx_raw_abnormal_move_symbol_date
    ON raw_abnormal_move (symbol, trade_date);

CREATE TABLE IF NOT EXISTS raw_dragon_tiger_seat (
    id              BIGSERIAL PRIMARY KEY,
    batch_id        TEXT NOT NULL,
    trade_date      TEXT NOT NULL,
    seat_name       TEXT NOT NULL,
    seat_code       TEXT,
    buy_count       INTEGER,
    sell_count      INTEGER,
    buy_amount      DOUBLE PRECISION,
    sell_amount     DOUBLE PRECISION,
    net_amount      DOUBLE PRECISION,
    related_stocks  TEXT,
    source_event_id TEXT NOT NULL,
    source          TEXT NOT NULL,
    ingested_at     TEXT NOT NULL,
    UNIQUE (trade_date, seat_name, source_event_id, source)
);

CREATE INDEX IF NOT EXISTS idx_raw_dragon_tiger_seat_date
    ON raw_dragon_tiger_seat (trade_date, net_amount);
