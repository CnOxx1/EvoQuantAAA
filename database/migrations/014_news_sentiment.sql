-- 新闻/论坛情绪原料：内容类型 + 扩展 JSON（得分、热度等）

ALTER TABLE raw_news_media
    ADD COLUMN IF NOT EXISTS content_type TEXT;

ALTER TABLE raw_news_media
    ADD COLUMN IF NOT EXISTS extra_json TEXT;

CREATE INDEX IF NOT EXISTS idx_raw_news_content_type
    ON raw_news_media (content_type);

CREATE INDEX IF NOT EXISTS idx_raw_news_channel_time
    ON raw_news_media (channel, publish_time);
