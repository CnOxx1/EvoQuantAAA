-- 阶段 21：实盘闸门适配器种子（fail-closed；无真实下单）

INSERT INTO execution_adapter_params (
    kind, enabled, allow_fills, require_live_env, meta_json, created_at
) VALUES (
    'live_gated',
    1,
    0,
    1,
    '{"note":"须 ASHARE_ALLOW_LIVE=1；武装后仍无 SDK 则 live_sdk_not_configured；永不成交"}',
    '2026-07-28T00:00:00+00:00'
) ON CONFLICT (kind) DO NOTHING;
