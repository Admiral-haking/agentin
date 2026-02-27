from __future__ import annotations

import ipaddress

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_session
from app.models.admin_user import AdminUser
from app.services.auth import AuthError, decode_token

security = HTTPBearer()


async def get_current_admin(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    session: AsyncSession = Depends(get_session),
) -> AdminUser:
    token = credentials.credentials
    try:
        payload = decode_token(token)
    except AuthError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc

    admin_id = payload.get("sub")
    if not admin_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    try:
        admin_id_int = int(admin_id)
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token") from exc

    result = await session.execute(select(AdminUser).where(AdminUser.id == admin_id_int))
    admin = result.scalars().first()
    if not admin or not admin.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Inactive user")
    return admin


def require_role(*roles: str):
    async def _guard(admin: AdminUser = Depends(get_current_admin)) -> AdminUser:
        if admin.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions",
            )
        return admin

    return _guard


async def get_request_ip(request: Request) -> str | None:
    def _valid_ip(raw: str | None) -> str | None:
        if not raw:
            return None
        try:
            return str(ipaddress.ip_address(raw.strip()))
        except ValueError:
            return None

    if settings.TRUST_PROXY_HEADERS:
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            for candidate in forwarded.split(","):
                parsed = _valid_ip(candidate)
                if parsed:
                    return parsed
        real_ip = _valid_ip(request.headers.get("x-real-ip"))
        if real_ip:
            return real_ip

    if request.client:
        return _valid_ip(request.client.host)
    return None
