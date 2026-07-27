from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ApiEnvelope:
    ok: bool
    data: Any = None
    error: dict[str, Any] | None = None
    meta: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {"ok": self.ok, "data": self.data}
        if self.error is not None:
            out["error"] = self.error
        if self.meta:
            out["meta"] = self.meta
        return out


def ok(data: Any = None, **meta: Any) -> dict[str, Any]:
    return ApiEnvelope(ok=True, data=data, meta=meta).to_dict()


def fail(code: str, message: str, *, status: int = 400, **meta: Any) -> dict[str, Any]:
    return ApiEnvelope(
        ok=False,
        error={"code": code, "message": message, "status": status},
        meta=meta,
    ).to_dict()
