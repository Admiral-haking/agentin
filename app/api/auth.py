from __future__ import annotations

from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_admin, get_request_ip
from app.core.config import settings
from app.core.database import get_session
from app.models.admin_refresh_token import AdminRefreshToken
from app.models.admin_user import AdminUser
from app.schemas.admin.auth import AdminUserOut, LoginRequest, RefreshRequest, TokenResponse
from app.services.auth import (
    AuthError,
    create_access_token,
    create_refresh_token,
    hash_refresh_token,
    verify_password,
)
from app.services.rate_limit import LoginRateLimiter
from app.utils.time import utc_now

router = APIRouter(prefix="/auth", tags=["auth"])

login_limiter = LoginRateLimiter(
    settings.LOGIN_RATE_LIMIT_MAX_ATTEMPTS,
    settings.LOGIN_RATE_LIMIT_WINDOW_SEC,
)


@router.post("/login", response_model=TokenResponse)
async def login(
    payload: LoginRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> TokenResponse:
    ip = await get_request_ip(request)
    limiter_key = ip or payload.username
    if not login_limiter.allow(limiter_key):
        raise HTTPException(status_code=429, detail="Too many login attempts")

    result = await session.execute(
        select(AdminUser).where(AdminUser.username == payload.username)
    )
    admin = result.scalars().first()
    if not admin or not admin.is_active:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    if not verify_password(payload.password, admin.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    access_token = create_access_token(str(admin.id), admin.role)
    refresh_token = create_refresh_token()
    refresh_hash = hash_refresh_token(refresh_token)

    admin.last_login_at = utc_now()

    record = AdminRefreshToken(
        admin_id=admin.id,
        token_hash=refresh_hash,
        expires_at=utc_now() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
        ip=ip,
        user_agent=request.headers.get("user-agent"),
    )
    session.add(record)
    await session.commit()

    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    payload: RefreshRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> TokenResponse:
    token_hash = hash_refresh_token(payload.refresh_token)
    result = await session.execute(
        select(AdminRefreshToken).where(AdminRefreshToken.token_hash == token_hash)
    )
    token = result.scalars().first()
    if not token or token.revoked_at or token.expires_at < utc_now():
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    admin = await session.get(AdminUser, token.admin_id)
    if not admin or not admin.is_active:
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    access_token = create_access_token(str(admin.id), admin.role)
    new_refresh = create_refresh_token()
    new_hash = hash_refresh_token(new_refresh)

    token.revoked_at = utc_now()
    token.last_used_at = utc_now()

    new_record = AdminRefreshToken(
        admin_id=admin.id,
        token_hash=new_hash,
        expires_at=utc_now() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
        ip=await get_request_ip(request),
        user_agent=request.headers.get("user-agent"),
    )
    session.add(new_record)
    await session.commit()

    return TokenResponse(access_token=access_token, refresh_token=new_refresh)


@router.get("/me", response_model=AdminUserOut)
async def me(admin: AdminUser = Depends(get_current_admin)) -> AdminUser:
    return admin
