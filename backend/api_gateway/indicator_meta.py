from __future__ import annotations

"""技术指标展示元数据：分类 / 主图·副图 / 线型。"""

from typing import Literal

Placement = Literal["overlay", "sub"]
Style = Literal["line", "hist"]

# pandas-ta Category 中文（前端展示）
CATEGORY_ZH: dict[str, str] = {
    "overlap": "重叠均线",
    "momentum": "动量振荡",
    "trend": "趋势",
    "volatility": "波动",
    "volume": "量能",
    "statistics": "统计",
    "cycle": "周期",
    "performance": "绩效",
    "candle": "K线衍生",
    "core": "核心",
    "unknown": "其他",
}

# 明确主图叠加（价格尺度）前缀 / 精确码
_OVERLAY_EXACT: frozenset[str] = frozenset(
    {
        "HL2",
        "HLC3",
        "OHLC4",
        "WCP",
    }
)

_OVERLAY_PREFIXES: tuple[str, ...] = (
    "MA_",
    "EMA_",
    "SMA_",
    "WMA_",
    "HMA_",
    "DEMA_",
    "TEMA_",
    "VWMA_",
    "VWAP_",
    "ALMA_",
    "RMA_",
    "SMMA_",
    "HWMA_",
    "FWMA_",
    "SWMA_",
    "PWMA_",
    "SINWMA_",
    "TRIMA_",
    "VIDYA_",
    "ZL_EMA_",
    "JMA_",
    "KAMA_",
    "MCGD_",
    "T3_",
    "BOLL_",
    "BB",
    "KC",
    "DC",
    "ACC",
    "SUPERT",
    "PSAR",
    "HA_",
    "MIDPOINT_",
    "MIDPRICE_",
    "LINREG_",
    "HIL",
    "ICS_",
    "IKS_",
    "ISA_",
    "ISB_",
    "ITS_",
    "CKSP",
)

_HIST_EXACT: frozenset[str] = frozenset(
    {
        "MACD_HIST",
        "MACDh_12_26_9",
        "PPOh_12_26_9",
        "PVOh_12_26_9",
        "STOCHh_14_3_3",
    }
)

_HIST_SUFFIXES: tuple[str, ...] = ("_HIST", "HIST")

# 手写 core 码 → 分类
_CORE_CAT: dict[str, str] = {
    "MA_5": "overlap",
    "MA_10": "overlap",
    "MA_20": "overlap",
    "MA_60": "overlap",
    "EMA_12": "overlap",
    "EMA_26": "overlap",
    "MACD_DIF": "momentum",
    "MACD_DEA": "momentum",
    "MACD_HIST": "momentum",
    "RSI_14": "momentum",
    "BOLL_MID": "volatility",
    "BOLL_UP": "volatility",
    "BOLL_LOW": "volatility",
}

# kind 前缀粗分（不依赖 pandas-ta 运行时）
_KIND_CAT_PREFIX: tuple[tuple[str, str], ...] = (
    ("MACD", "momentum"),
    ("RSI", "momentum"),
    ("STOCH", "momentum"),
    ("CCI", "momentum"),
    ("WILLR", "momentum"),
    ("MOM", "momentum"),
    ("ROC", "momentum"),
    ("CMO", "momentum"),
    ("TSI", "momentum"),
    ("UO_", "momentum"),
    ("AO_", "momentum"),
    ("APO_", "momentum"),
    ("PPO", "momentum"),
    ("QQE", "momentum"),
    ("FISH", "momentum"),
    ("CTI", "momentum"),
    ("BIAS", "momentum"),
    ("BR_", "momentum"),
    ("AR_", "momentum"),
    ("ADX", "trend"),
    ("ADXR", "trend"),
    ("AROON", "trend"),
    ("DMN_", "trend"),
    ("DMP_", "trend"),
    ("VTX", "trend"),
    ("PSAR", "trend"),
    ("SUPERT", "trend"),
    ("CHOP", "trend"),
    ("QSTICK", "trend"),
    ("QS_", "trend"),
    ("ATR", "volatility"),
    ("NATR", "volatility"),
    ("BOLL", "volatility"),
    ("BB", "volatility"),
    ("KC", "volatility"),
    ("DC", "volatility"),
    ("ACC", "volatility"),
    ("MASS", "volatility"),
    ("UI_", "volatility"),
    ("OBV", "volume"),
    ("AD", "volume"),
    ("ADOSC", "volume"),
    ("CMF", "volume"),
    ("MFI", "volume"),
    ("EFI", "volume"),
    ("EOM", "volume"),
    ("KVO", "volume"),
    ("NVI", "volume"),
    ("PVO", "volume"),
    ("PVOL", "volume"),
    ("PVR", "volume"),
    ("PVT", "volume"),
    ("VWAP", "volume"),
    ("VWMA", "volume"),
    ("MA_", "overlap"),
    ("EMA_", "overlap"),
    ("SMA_", "overlap"),
    ("WMA_", "overlap"),
    ("HMA_", "overlap"),
    ("DEMA", "overlap"),
    ("TEMA", "overlap"),
    ("ALMA", "overlap"),
    ("HA_", "candle"),
    ("CDL", "candle"),
    ("Z_", "statistics"),
    ("STDEV", "statistics"),
    ("VAR_", "statistics"),
    ("SKEW", "statistics"),
    ("KURT", "statistics"),
    ("MAD_", "statistics"),
    ("MEDIAN", "statistics"),
    ("QTL_", "statistics"),
    ("ENTP", "statistics"),
    ("LOGRET", "performance"),
    ("PCTRET", "performance"),
)


def guess_category(code: str) -> str:
    c = (code or "").strip()
    if not c:
        return "unknown"
    if c in _CORE_CAT:
        return _CORE_CAT[c]
    cu = c.upper()
    for pref, cat in _KIND_CAT_PREFIX:
        if cu.startswith(pref.upper()):
            return cat
    return "unknown"


def guess_placement(code: str, category: str | None = None) -> Placement:
    c = (code or "").strip()
    cu = c.upper()
    if cu in {x.upper() for x in _OVERLAY_EXACT}:
        return "overlay"
    for p in _OVERLAY_PREFIXES:
        if cu.startswith(p.upper()):
            return "overlay"
    cat = category or guess_category(c)
    if cat in ("overlap", "candle"):
        return "overlay"
    return "sub"


def guess_style(code: str) -> Style:
    c = (code or "").strip()
    cu = c.upper()
    if cu in {x.upper() for x in _HIST_EXACT}:
        return "hist"
    for suf in _HIST_SUFFIXES:
        if cu.endswith(suf.upper()):
            return "hist"
    # pandas-ta MACDh / PPOh 等
    if "H_" in cu and cu.split("_", 1)[0].endswith("H"):
        return "hist"
    if cu.startswith("MACDH") or cu.startswith("PPOH") or cu.startswith("PVOH"):
        return "hist"
    return "line"


def enrich_indicator_code(code: str, *, count: int = 0) -> dict[str, object]:
    cat = guess_category(code)
    place = guess_placement(code, cat)
    style = guess_style(code)
    return {
        "code": code,
        "count": int(count),
        "category": cat,
        "category_zh": CATEGORY_ZH.get(cat, CATEGORY_ZH["unknown"]),
        "placement": place,
        "style": style,
    }
