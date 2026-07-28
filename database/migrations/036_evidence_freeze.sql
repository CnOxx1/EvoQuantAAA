-- 阶段 19：研究证据包冻结（长窗 OOS 固化产物）

CREATE TABLE IF NOT EXISTS research_evidence_freeze (
    freeze_id         TEXT PRIMARY KEY,
    evidence_run_id   TEXT NOT NULL,
    universe_code     TEXT NOT NULL,
    start_date        TEXT NOT NULL,
    end_date          TEXT NOT NULL,
    status            TEXT NOT NULL,
    split_mode        TEXT NOT NULL,
    hard_gates_json   TEXT,
    summary_json      TEXT NOT NULL,
    artifact_hash     TEXT NOT NULL,
    actor             TEXT,
    reason            TEXT,
    job_id            TEXT,
    meta_json         TEXT,
    created_at        TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_research_evidence_freeze_run
    ON research_evidence_freeze (evidence_run_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_research_evidence_freeze_univ
    ON research_evidence_freeze (universe_code, status, created_at DESC);

CREATE UNIQUE INDEX IF NOT EXISTS uq_research_evidence_freeze_hash_active
    ON research_evidence_freeze (artifact_hash)
    WHERE status = 'frozen';
