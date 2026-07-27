from __future__ import annotations

import os
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from api_gateway.auth import check_bearer, expected_token
from api_gateway.models import fail, ok


def _run_mock() -> None:
    assert ok({"a": 1})["ok"] is True
    assert fail("X", "msg", status=404)["ok"] is False
    assert fail("X", "msg")["error"]["status"] == 400

    os.environ.pop("ASHARE_API_TOKEN", None)
    assert check_bearer(None)[0] is True

    os.environ["ASHARE_API_TOKEN"] = "secret"
    assert check_bearer(None)[0] is False
    assert check_bearer("Bearer secret")[0] is True
    assert check_bearer("Bearer wrong")[0] is False
    assert expected_token() == "secret"
    os.environ.pop("ASHARE_API_TOKEN", None)
    print("mock_cases=ok")


def main() -> int:
    _run_mock()
    print("status=ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
