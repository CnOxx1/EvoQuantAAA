-- 阶段 18a：风控 ADV 参与度与行业集中度限额

ALTER TABLE risk_limits
    ADD COLUMN IF NOT EXISTS max_industry_weight DOUBLE PRECISION;

ALTER TABLE risk_limits
    ADD COLUMN IF NOT EXISTS max_adv_participation DOUBLE PRECISION;

ALTER TABLE risk_limits
    ADD COLUMN IF NOT EXISTS adv_lookback_days INTEGER;

ALTER TABLE risk_limits
    ADD COLUMN IF NOT EXISTS industry_standard TEXT;

INSERT INTO risk_limits (
    version, max_single_weight, max_names, max_gross_exposure, min_names,
    max_industry_weight, max_adv_participation, adv_lookback_days, industry_standard,
    meta_json, created_at
) VALUES (
    'v2_adv_industry',
    0.15,
    50,
    1.01,
    1,
    0.30,
    0.10,
    20,
    'SW2021',
    '{"note":"单票<=15%; 行业<=30% NAV; 单票目标市值<=10% 的20日均成交额(ADV)"}',
    '2026-07-28T00:00:00+00:00'
) ON CONFLICT (version) DO NOTHING;
