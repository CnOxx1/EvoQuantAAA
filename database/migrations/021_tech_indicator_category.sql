-- 技术指标分类（pandas-ta Category）；兼容已有 core 长表行

ALTER TABLE processed_tech_indicator_1d
    ADD COLUMN IF NOT EXISTS category TEXT;

CREATE INDEX IF NOT EXISTS idx_tech_indicator_category
    ON processed_tech_indicator_1d (category, trade_date);

COMMENT ON COLUMN processed_tech_indicator_1d.category IS
    'candle|cycle|momentum|overlap|performance|statistics|trend|volatility|volume|core';
