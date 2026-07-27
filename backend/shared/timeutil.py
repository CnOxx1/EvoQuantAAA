from __future__ import annotations

from datetime import datetime, timedelta, timezone


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def normalize_publish_time(value: object) -> str:
    """统一为可比较的 UTC ISO8601 字符串。"""
    if value is None or value == "":
        raise ValueError("publish_time 为空")
    if isinstance(value, (int, float)):
        ts = float(value)
        # 毫秒 / 秒
        if ts > 1e12:
            ts /= 1000.0
        return datetime.fromtimestamp(ts, tz=timezone.utc).replace(microsecond=0).isoformat()

    text = str(value).strip()
    if text.isdigit():
        return normalize_publish_time(int(text))

    # 常见：2026-07-24 15:00:00 / 2026-07-24T15:00:00
    for fmt in (
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d",
    ):
        try:
            dt = datetime.strptime(text.replace("Z", "+0000"), fmt.replace("%z", "%z"))
            if dt.tzinfo is None:
                # 巨潮网页时间按东八区理解
                dt = dt.replace(tzinfo=timezone(timedelta(hours=8)))
            return dt.astimezone(timezone.utc).replace(microsecond=0).isoformat()
        except ValueError:
            continue
    # 兜底：原样返回（尽量避免），调用方应保证可比较
    return text


def default_se_date(start: str | None, end: str | None, *, lookback_days: int = 7) -> str:
    if start and end:
        return f"{start[:10]}~{end[:10]}"
    if start and not end:
        return f"{start[:10]}~{start[:10]}"
    if end and not start:
        return f"{end[:10]}~{end[:10]}"
    today = datetime.now(timezone(timedelta(hours=8))).date()
    begin = today - timedelta(days=lookback_days)
    return f"{begin.isoformat()}~{today.isoformat()}"
