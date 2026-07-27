-- 阶段 4：运维告警（schedule 编排不另建业务表，只用 job_id 串联）

CREATE TABLE IF NOT EXISTS ops_alert (
    alert_id     TEXT PRIMARY KEY,
    job_id       TEXT,
    severity     TEXT NOT NULL,
    source       TEXT NOT NULL,
    ref_id       TEXT,
    message      TEXT NOT NULL,
    detail_json  TEXT,
    status       TEXT NOT NULL DEFAULT 'open',
    created_at   TIMESTAMPTZ NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_ops_alert_job
    ON ops_alert (job_id, created_at);
CREATE INDEX IF NOT EXISTS idx_ops_alert_status
    ON ops_alert (status, created_at);
