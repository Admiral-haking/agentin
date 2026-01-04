from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.campaign import Campaign
from app.utils.time import utc_now


async def get_active_campaigns(session: AsyncSession, limit: int = 5) -> list[Campaign]:
    now = utc_now()
    query = (
        select(Campaign)
        .where(Campaign.active.is_(True))
        .where((Campaign.start_at.is_(None)) | (Campaign.start_at <= now))
        .where((Campaign.end_at.is_(None)) | (Campaign.end_at >= now))
        .order_by(Campaign.priority.desc(), Campaign.created_at.desc())
        .limit(limit)
    )
    result = await session.execute(query)
    return list(result.scalars().all())
