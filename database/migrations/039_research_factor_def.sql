-- 039 research_factor_def: 可注册/修改的因子定义（模板 + 参数），供 UI / gateway 管理
CREATE TABLE IF NOT EXISTS research_factor_def (
    factor_code   TEXT PRIMARY KEY,
    display_name  TEXT NOT NULL DEFAULT '',
    template      TEXT NOT NULL,
    params_json   TEXT NOT NULL DEFAULT '{}',
    description   TEXT,
    status        TEXT NOT NULL DEFAULT 'ACTIVE',
    is_builtin    INTEGER NOT NULL DEFAULT 0,
    created_by    TEXT,
    created_at    TEXT NOT NULL,
    updated_at    TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_research_factor_def_status
    ON research_factor_def (status, template);

-- 注意：勿写 {"lookback":20} 字面量（SQLAlchemy 会把 :20 当 bind）
INSERT INTO research_factor_def (
    factor_code, display_name, template, params_json, description,
    status, is_builtin, created_by, created_at, updated_at
) VALUES
(
    'MOM_20', '动量 20 日', 'MOM', json_build_object('lookback', 20)::text,
    'adj_close_t / adj_close_{t-N} - 1',
    'ACTIVE', 1, 'seed', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
),
(
    'VAL_PE_PCT', 'PE 截面分位', 'VAL_PE_PCT', '{}',
    'Universe 内 PE-TTM 截面分位',
    'ACTIVE', 1, 'seed', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
),
(
    'FLOW_NET_5', '主力净流入 5 日', 'FLOW_NET', json_build_object('lookback', 5)::text,
    '近 N 日主力净流入 / 成交额',
    'ACTIVE', 1, 'seed', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
),
(
    'TECH_RSI_14', 'RSI 14', 'TECH_RSI', json_build_object('period', 14)::text,
    '透传 processed RSI_{period}',
    'ACTIVE', 1, 'seed', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
),
(
    'TECH_MACD_HIST', 'MACD 柱', 'TECH_MACD_HIST', '{}',
    '透传 MACD_HIST',
    'ACTIVE', 1, 'seed', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
),
(
    'TECH_MA20_BIAS', '均线乖离', 'TECH_MA_BIAS', json_build_object('period', 20)::text,
    'adj_close / MA_{period} - 1',
    'ACTIVE', 1, 'seed', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
)
ON CONFLICT (factor_code) DO NOTHING;
