from __future__ import annotations

import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from strategy_registry.transitions import can_transition, validate_transition


def _run_mock() -> None:
    assert can_transition("DRAFT", "BACKTESTED")
    assert can_transition("BACKTESTED", "PAPER")
    assert can_transition("PAPER", "LIVE")
    assert can_transition("LIVE", "RETIRED")
    assert not can_transition("DRAFT", "LIVE")
    assert not can_transition("RETIRED", "PAPER")
    assert validate_transition("DRAFT", "LIVE") is not None
    assert validate_transition("PAPER", "LIVE") is None
    assert validate_transition("RETIRED", "LIVE") is not None
    print("mock_cases=ok")


def main() -> int:
    _run_mock()
    print("status=ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
