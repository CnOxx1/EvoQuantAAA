from __future__ import annotations

"""
实盘环境闸门（纯函数）。

- 未武装：禁止走 require_live_env=1 的适配器路径
- 武装后：仍不代表可真实下单；具体适配器须另接券商 SDK 且 allow_fills 另行打开
- 本模块不读密钥、不发起网络
"""

import os

LIVE_ENV_FLAG = "ASHARE_ALLOW_LIVE"
LIVE_ENV_NOT_ARMED = "live_env_not_armed"
LIVE_SDK_NOT_CONFIGURED = "live_sdk_not_configured"


def is_live_armed(environ: dict[str, str] | None = None) -> bool:
    """仅当 ASHARE_ALLOW_LIVE∈{1,true,yes,on}（大小写不敏感）视为武装。"""
    src = environ if environ is not None else os.environ
    raw = str(src.get(LIVE_ENV_FLAG, "") or "").strip().lower()
    return raw in {"1", "true", "yes", "on"}


def check_live_env_gate(
    *,
    require_live_env: bool,
    environ: dict[str, str] | None = None,
) -> tuple[bool, str | None]:
    """
    返回 (ok, reason)。
    require_live_env=False 时始终 ok。
    """
    if not require_live_env:
        return True, None
    if is_live_armed(environ):
        return True, None
    return False, (
        f"{LIVE_ENV_NOT_ARMED}: set {LIVE_ENV_FLAG}=1 to arm live path "
        f"(still fail-closed until vendor SDK is configured)"
    )
