-- 上市公司重大合同 / 中标事件（ALPHA）

CREATE TABLE IF NOT EXISTS raw_major_contract (
    id                      BIGSERIAL PRIMARY KEY,
    batch_id                TEXT NOT NULL,
    symbol                  TEXT NOT NULL,
    name                    TEXT,
    announce_date           TEXT NOT NULL,
    sign_date               TEXT,
    contract_type           TEXT,
    contract_name           TEXT,
    amount                  DOUBLE PRECISION,
    revenue_prev_year       DOUBLE PRECISION,
    amount_rev_ratio        DOUBLE PRECISION,
    revenue_latest          DOUBLE PRECISION,
    party_self              TEXT,
    party_self_relation     TEXT,
    party_other             TEXT,
    party_other_relation    TEXT,
    is_win_bid              INTEGER NOT NULL DEFAULT 0,
    source_event_id         TEXT NOT NULL,
    source                  TEXT NOT NULL,
    ingested_at             TEXT NOT NULL,
    UNIQUE (symbol, announce_date, source_event_id, source)
);

CREATE INDEX IF NOT EXISTS idx_raw_major_contract_announce
    ON raw_major_contract (announce_date);
CREATE INDEX IF NOT EXISTS idx_raw_major_contract_symbol_date
    ON raw_major_contract (symbol, announce_date);
CREATE INDEX IF NOT EXISTS idx_raw_major_contract_win_bid
    ON raw_major_contract (is_win_bid, announce_date);
