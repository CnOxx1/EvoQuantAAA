from __future__ import annotations

"""日线技术指标：core 手写子集 + full（pandas-ta 全部分类）。不连库。"""

from collections import defaultdict
from typing import Any

from data_process.tech_catalog import (
    CORE_LOOKBACK_CALENDAR_DAYS,
    FULL_LOOKBACK_CALENDAR_DAYS,
    SUITE_CORE,
    SUITE_FULL,
    build_study,
    categorize_column,
    kind_to_category_map,
    load_pandas_ta_kinds,
)

# 兼容旧码：日更 / suite=core
INDICATOR_CODES: tuple[str, ...] = (
    "MA_5",
    "MA_10",
    "MA_20",
    "MA_60",
    "EMA_12",
    "EMA_26",
    "MACD_DIF",
    "MACD_DEA",
    "MACD_HIST",
    "RSI_14",
    "BOLL_MID",
    "BOLL_UP",
    "BOLL_LOW",
)

LOOKBACK_CALENDAR_DAYS = CORE_LOOKBACK_CALENDAR_DAYS


def lookback_days_for_suite(suite: str) -> int:
    if suite == SUITE_FULL:
        return FULL_LOOKBACK_CALENDAR_DAYS
    return CORE_LOOKBACK_CALENDAR_DAYS


def _sma(window: list[float]) -> float | None:
    if not window:
        return None
    return sum(window) / len(window)


def _rolling_std(window: list[float]) -> float | None:
    n = len(window)
    if n < 1:
        return None
    mean = sum(window) / n
    var = sum((x - mean) ** 2 for x in window) / n
    return var**0.5


def _ema_series(values: list[float], span: int) -> list[float | None]:
    out: list[float | None] = [None] * len(values)
    if span < 1 or len(values) < span:
        return out
    alpha = 2.0 / (span + 1)
    seed = sum(values[:span]) / span
    out[span - 1] = seed
    prev = seed
    for i in range(span, len(values)):
        prev = alpha * values[i] + (1.0 - alpha) * prev
        out[i] = prev
    return out


def _rsi_series(values: list[float], period: int = 14) -> list[float | None]:
    n = len(values)
    out: list[float | None] = [None] * n
    if n < period + 1:
        return out
    gains = [0.0] * n
    losses = [0.0] * n
    for i in range(1, n):
        d = values[i] - values[i - 1]
        gains[i] = max(d, 0.0)
        losses[i] = max(-d, 0.0)
    avg_gain = sum(gains[1 : period + 1]) / period
    avg_loss = sum(losses[1 : period + 1]) / period
    if avg_loss == 0:
        out[period] = 100.0
    else:
        rs = avg_gain / avg_loss
        out[period] = 100.0 - (100.0 / (1.0 + rs))
    for i in range(period + 1, n):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
        if avg_loss == 0:
            out[i] = 100.0
        else:
            rs = avg_gain / avg_loss
            out[i] = 100.0 - (100.0 / (1.0 + rs))
    return out


def compute_for_closes(closes: list[float]) -> dict[str, list[float | None]]:
    n = len(closes)
    ma5 = [None] * n
    ma10 = [None] * n
    ma20 = [None] * n
    ma60 = [None] * n
    boll_mid = [None] * n
    boll_up = [None] * n
    boll_low = [None] * n
    for i in range(n):
        if i + 1 >= 5:
            ma5[i] = _sma(closes[i - 4 : i + 1])
        if i + 1 >= 10:
            ma10[i] = _sma(closes[i - 9 : i + 1])
        if i + 1 >= 20:
            mid = _sma(closes[i - 19 : i + 1])
            std = _rolling_std(closes[i - 19 : i + 1])
            ma20[i] = mid
            boll_mid[i] = mid
            if mid is not None and std is not None:
                boll_up[i] = mid + 2.0 * std
                boll_low[i] = mid - 2.0 * std
        if i + 1 >= 60:
            ma60[i] = _sma(closes[i - 59 : i + 1])

    ema12 = _ema_series(closes, 12)
    ema26 = _ema_series(closes, 26)
    dif: list[float | None] = [None] * n
    for i in range(n):
        if ema12[i] is not None and ema26[i] is not None:
            dif[i] = float(ema12[i]) - float(ema26[i])

    dea = [None] * n
    dif_vals: list[float] = []
    dif_idx: list[int] = []
    for i, v in enumerate(dif):
        if v is not None:
            dif_vals.append(v)
            dif_idx.append(i)
    dea_series = _ema_series(dif_vals, 9)
    for j, idx in enumerate(dif_idx):
        dea[idx] = dea_series[j]

    hist: list[float | None] = [None] * n
    for i in range(n):
        if dif[i] is not None and dea[i] is not None:
            hist[i] = float(dif[i]) - float(dea[i])

    rsi = _rsi_series(closes, 14)
    return {
        "MA_5": ma5,
        "MA_10": ma10,
        "MA_20": ma20,
        "MA_60": ma60,
        "EMA_12": ema12,
        "EMA_26": ema26,
        "MACD_DIF": dif,
        "MACD_DEA": dea,
        "MACD_HIST": hist,
        "RSI_14": rsi,
        "BOLL_MID": boll_mid,
        "BOLL_UP": boll_up,
        "BOLL_LOW": boll_low,
    }


def _bar_ts(row: dict[str, Any]) -> str:
    if row.get("bar_time"):
        return str(row["bar_time"])
    return str(row.get("trade_date") or "")[:10]


def _in_range(ts: str, start: str, end: str, *, freq: str) -> bool:
    if freq == "1d":
        d = ts[:10]
        return start[:10] <= d <= end[:10]
    lo = f"{start[:10]} 00:00:00"
    hi = f"{end[:10]} 23:59:59"
    return lo <= ts[:19] <= hi


def compute_tech_indicator_rows(
    bars: list[dict[str, Any]],
    *,
    start: str,
    end: str,
    factor_type: str,
    process_batch_id: str,
    processed_at: str,
    source: str = "processed_equity_bar_1d",
    suite: str = SUITE_CORE,
    categories: list[str] | None = None,
    freq: str = "1d",
) -> list[dict[str, Any]]:
    if suite == SUITE_FULL:
        return _compute_full_rows(
            bars,
            start=start,
            end=end,
            factor_type=factor_type,
            process_batch_id=process_batch_id,
            processed_at=processed_at,
            source=source,
            categories=categories,
            freq=freq,
        )
    return _compute_core_rows(
        bars,
        start=start,
        end=end,
        factor_type=factor_type,
        process_batch_id=process_batch_id,
        processed_at=processed_at,
        source=source,
        freq=freq,
    )


def _emit_row(
    *,
    process_batch_id: str,
    symbol: str,
    ts: str,
    factor_type: str,
    indicator_code: str,
    value: float,
    category: str,
    source: str,
    processed_at: str,
    freq: str,
) -> dict[str, Any]:
    row: dict[str, Any] = {
        "process_batch_id": process_batch_id,
        "symbol": symbol,
        "factor_type": factor_type,
        "indicator_code": indicator_code,
        "value": value,
        "category": category,
        "source": source,
        "processed_at": processed_at,
        "freq": freq,
    }
    if freq == "1d":
        row["trade_date"] = ts[:10]
    else:
        row["bar_time"] = ts[:19] if len(ts) >= 19 else ts
    return row


def _compute_core_rows(
    bars: list[dict[str, Any]],
    *,
    start: str,
    end: str,
    factor_type: str,
    process_batch_id: str,
    processed_at: str,
    source: str,
    freq: str,
) -> list[dict[str, Any]]:
    by_sym: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for b in bars:
        if b.get("adj_close") is None:
            continue
        by_sym[str(b["symbol"])].append(b)

    out: list[dict[str, Any]] = []
    for symbol, rows in by_sym.items():
        rows = sorted(rows, key=_bar_ts)
        stamps = [_bar_ts(r) for r in rows]
        closes = [float(r["adj_close"]) for r in rows]
        series = compute_for_closes(closes)
        for i, ts in enumerate(stamps):
            if not _in_range(ts, start, end, freq=freq):
                continue
            for code in INDICATOR_CODES:
                val = series[code][i]
                if val is None:
                    continue
                out.append(
                    _emit_row(
                        process_batch_id=process_batch_id,
                        symbol=symbol,
                        ts=ts,
                        factor_type=factor_type,
                        indicator_code=code,
                        value=float(val),
                        category="core",
                        source=source,
                        processed_at=processed_at,
                        freq=freq,
                    )
                )
    return out


def _ohlcv_frame(rows: list[dict[str, Any]]):
    import pandas as pd

    records = []
    for r in rows:
        ac = r.get("adj_close")
        if ac is None:
            continue
        ao = r.get("adj_open")
        ah = r.get("adj_high")
        al = r.get("adj_low")
        c = float(ac)
        records.append(
            {
                "ts": _bar_ts(r),
                "open": float(ao) if ao is not None else c,
                "high": float(ah) if ah is not None else c,
                "low": float(al) if al is not None else c,
                "close": c,
                "volume": float(r["volume"]) if r.get("volume") is not None else 0.0,
            }
        )
    if not records:
        return None
    df = pd.DataFrame.from_records(records)
    df["ts"] = pd.to_datetime(df["ts"])
    df = df.set_index("ts").sort_index()
    return df


def _compute_full_rows(
    bars: list[dict[str, Any]],
    *,
    start: str,
    end: str,
    factor_type: str,
    process_batch_id: str,
    processed_at: str,
    source: str,
    categories: list[str] | None,
    freq: str,
) -> list[dict[str, Any]]:
    import numpy as np

    kinds = load_pandas_ta_kinds(categories=categories)
    if not kinds:
        return []
    kind_map = kind_to_category_map(kinds)
    study = build_study(kinds)

    by_sym: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for b in bars:
        by_sym[str(b["symbol"])].append(b)

    out: list[dict[str, Any]] = []
    base_cols = {"open", "high", "low", "close", "volume"}
    for symbol, rows in by_sym.items():
        rows = sorted(rows, key=_bar_ts)
        df = _ohlcv_frame(rows)
        if df is None or len(df) < 5:
            continue
        work = df.copy()
        try:
            work.ta.study(study, verbose=False)
        except Exception:  # noqa: BLE001
            continue

        ind_cols = [c for c in work.columns if c not in base_cols]
        for ts, row in work.iterrows():
            stamp = pd_timestamp_to_str(ts, freq=freq)
            if not _in_range(stamp, start, end, freq=freq):
                continue
            for col in ind_cols:
                val = row[col]
                if val is None or (isinstance(val, float) and np.isnan(val)):
                    continue
                try:
                    fval = float(val)
                except (TypeError, ValueError):
                    continue
                if np.isnan(fval) or np.isinf(fval):
                    continue
                out.append(
                    _emit_row(
                        process_batch_id=process_batch_id,
                        symbol=symbol,
                        ts=stamp,
                        factor_type=factor_type,
                        indicator_code=str(col),
                        value=fval,
                        category=categorize_column(str(col), kind_map),
                        source=source,
                        processed_at=processed_at,
                        freq=freq,
                    )
                )
    return out


def pd_timestamp_to_str(ts: Any, *, freq: str) -> str:
    import pandas as pd

    if isinstance(ts, pd.Timestamp):
        if freq == "1d":
            return ts.strftime("%Y-%m-%d")
        return ts.strftime("%Y-%m-%d %H:%M:%S")
    s = str(ts)
    return s[:10] if freq == "1d" else s[:19]
