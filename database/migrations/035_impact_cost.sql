-- 阶段 18b：成交冲击成本（sqrt ADV 参与度）

ALTER TABLE cost_params
    ADD COLUMN IF NOT EXISTS impact_model TEXT;

ALTER TABLE cost_params
    ADD COLUMN IF NOT EXISTS impact_coef DOUBLE PRECISION;

ALTER TABLE cost_params
    ADD COLUMN IF NOT EXISTS adv_lookback_days INTEGER;

UPDATE cost_params
SET impact_model = COALESCE(impact_model, 'flat'),
    impact_coef = COALESCE(impact_coef, 0),
    adv_lookback_days = COALESCE(adv_lookback_days, 20)
WHERE version = 'v1_ashare_default';

INSERT INTO cost_params (
    version, commission_rate, min_commission, stamp_tax_rate,
    slippage_rate, lot_size, impact_model, impact_coef, adv_lookback_days,
    meta_json, created_at
) VALUES (
    'v2_sqrt_impact',
    0.0003,
    5.0,
    0.0005,
    0.0005,
    100,
    'sqrt_adv',
    0.1,
    20,
    '{"note":"基滑点万五 + 0.1*sqrt(名义/ADV20)；ADV 缺失时退回仅基滑点"}',
    '2026-07-28T00:00:00+00:00'
) ON CONFLICT (version) DO NOTHING;
