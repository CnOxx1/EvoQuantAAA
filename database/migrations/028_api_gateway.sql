-- api_gateway：可选审计日志（写操作留痕）

CREATE TABLE IF NOT EXISTS api_audit_log (
    audit_id       TEXT PRIMARY KEY,
    actor          TEXT,
    method         TEXT NOT NULL,
    path           TEXT NOT NULL,
    status_code    INTEGER,
    request_json   TEXT,
    result_json    TEXT,
    created_at     TIMESTAMPTZ NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_api_audit_log_created
    ON api_audit_log (created_at DESC);
