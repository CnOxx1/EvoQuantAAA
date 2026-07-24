-- alpha_flow ALPHA 资金与活跃度表（PostgreSQL）

CREATE TABLE IF NOT EXISTS raw_money_flow (
    id              BIGSERIAL PRIMARY KEY,
    batch_id        TEXT NOT NULL,
    scope           TEXT NOT NULL,
    trade_date      TEXT NOT NULL,
    flow_type       TEXT NOT NULL,
    net_amount      DOUBLE PRECISION,
    buy_amount      DOUBLE PRECISION,
    sell_amount     DOUBLE PRECISION,
    extra_json      TEXT,
    source          TEXT NOT NULL,
    ingested_at     TEXT NOT NULL,
    UNIQUE (scope, trade_date, flow_type, source)
);

CREATE TABLE IF NOT EXISTS raw_margin (
    id              BIGSERIAL PRIMARY KEY,
    batch_id        TEXT NOT NULL,
    symbol          TEXT NOT NULL,
    trade_date      TEXT NOT NULL,
    rzye            DOUBLE PRECISION,
    rqye            DOUBLE PRECISION,
    rzmre           DOUBLE PRECISION,
    rqyl            DOUBLE PRECISION,
    rzche           DOUBLE PRECISION,
    rqchl           DOUBLE PRECISION,
    rzrqye          DOUBLE PRECISION,
    source          TEXT NOT NULL,
    ingested_at     TEXT NOT NULL,
    UNIQUE (symbol, trade_date, source)
);

CREATE TABLE IF NOT EXISTS raw_dragon_tiger (
    id              BIGSERIAL PRIMARY KEY,
    batch_id        TEXT NOT NULL,
    symbol          TEXT NOT NULL,
    trade_date      TEXT NOT NULL,
    reason          TEXT,
    close           DOUBLE PRECISION,
    pct_chg         DOUBLE PRECISION,
    net_amount      DOUBLE PRECISION,
    buy_amount      DOUBLE PRECISION,
    sell_amount     DOUBLE PRECISION,
    source_event_id TEXT NOT NULL,
    source          TEXT NOT NULL,
    ingested_at     TEXT NOT NULL,
    UNIQUE (symbol, trade_date, source_event_id, source)
);

CREATE TABLE IF NOT EXISTS raw_block_trade (
    id              BIGSERIAL PRIMARY KEY,
    batch_id        TEXT NOT NULL,
    symbol          TEXT NOT NULL,
    trade_date      TEXT NOT NULL,
    price           DOUBLE PRECISION,
    volume          DOUBLE PRECISION,
    amount          DOUBLE PRECISION,
    premium_rate    DOUBLE PRECISION,
    buyer           TEXT,
    seller          TEXT,
    source_event_id TEXT NOT NULL,
    source          TEXT NOT NULL,
    ingested_at     TEXT NOT NULL,
    UNIQUE (symbol, trade_date, source_event_id, source)
);
