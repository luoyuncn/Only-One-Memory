"""管理 API 的可选 API Key 校验，本地未配置时保持开放。"""

from __future__ import annotations

import hmac
from dataclasses import dataclass

from fastapi import HTTPException, Request, status

from oom.memory_core.config import AppConfig


@dataclass(frozen=True)
class ApiPrincipal:
    """通过鉴权后的调用方身份，后续可以扩展更多 scope。"""

    actor: str
    scopes: frozenset[str]


def _configured_key(config: AppConfig) -> str | None:
    key = config.security.api_key
    return key if key else None


async def require_api_key(request: Request, required_scope: str = "admin") -> ApiPrincipal:
    """校验 Bearer API Key；未配置 key 时返回开发态 principal。"""
    config = getattr(request.app.state, "config", AppConfig())
    expected = _configured_key(config)
    if expected is None:
        return ApiPrincipal(actor="api-key:disabled", scopes=frozenset({"admin"}))

    scheme, _, token = request.headers.get("Authorization", "").partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="missing api key")
    if not hmac.compare_digest(token, expected):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid api key")

    scopes = frozenset({"admin"})
    if required_scope not in scopes:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="insufficient scope")
    return ApiPrincipal(actor="api-key:default", scopes=scopes)
