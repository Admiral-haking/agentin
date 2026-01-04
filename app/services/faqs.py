from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.faq import Faq


async def get_verified_faqs(session: AsyncSession, limit: int = 30) -> list[Faq]:
    result = await session.execute(
        select(Faq)
        .where(Faq.verified.is_(True))
        .order_by(Faq.created_at.desc())
        .limit(limit)
    )
    return list(result.scalars().all())
