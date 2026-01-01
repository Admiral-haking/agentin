from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.admin.utils import list_response, parse_filter
from app.api.deps import get_request_ip, require_role
from app.core.database import get_session
from app.models.campaign import Campaign
from app.schemas.admin.campaign import CampaignCreate, CampaignOut, CampaignUpdate
from app.services.audit import record_audit

router = APIRouter(prefix="/admin/campaigns", tags=["admin"])


@router.get("", response_model=dict)
async def list_campaigns(
    request: Request,
    skip: int = 0,
    limit: int = 25,
    sort: str = "created_at",
    order: str = "desc",
    filter: str | None = None,
    session: AsyncSession = Depends(get_session),
    admin=Depends(require_role("admin", "staff")),
) -> dict:
    filters = parse_filter(filter)
    query = select(Campaign)
    if "id" in filters:
        ids = filters["id"]
        if isinstance(ids, list):
            query = query.where(Campaign.id.in_(ids))
    if "active" in filters:
        query = query.where(Campaign.active == bool(filters["active"]))
    if "q" in filters:
        q = f"%{filters['q']}%"
        query = query.where(Campaign.title.ilike(q) | Campaign.body.ilike(q))

    sort_col = getattr(Campaign, sort, Campaign.created_at)
    if order.lower() == "desc":
        query = query.order_by(sort_col.desc())
    else:
        query = query.order_by(sort_col.asc())

    total = await session.scalar(select(func.count()).select_from(query.subquery()))
    result = await session.execute(query.offset(skip).limit(limit))
    items = [CampaignOut.model_validate(item) for item in result.scalars().all()]
    return list_response(items, total or 0)


@router.get("/{campaign_id}", response_model=CampaignOut)
async def get_campaign(
    campaign_id: int,
    session: AsyncSession = Depends(get_session),
    admin=Depends(require_role("admin", "staff")),
) -> CampaignOut:
    campaign = await session.get(Campaign, campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    return CampaignOut.model_validate(campaign)


@router.post("", response_model=CampaignOut)
async def create_campaign(
    payload: CampaignCreate,
    request: Request,
    session: AsyncSession = Depends(get_session),
    admin=Depends(require_role("admin", "staff")),
) -> CampaignOut:
    campaign = Campaign(**payload.model_dump())
    session.add(campaign)
    await session.commit()

    await record_audit(
        session,
        admin_id=admin.id,
        entity="campaigns",
        action="create",
        before=None,
        after=campaign,
        ip=await get_request_ip(request),
        user_agent=request.headers.get("user-agent"),
    )

    return CampaignOut.model_validate(campaign)


@router.put("/{campaign_id}", response_model=CampaignOut)
async def update_campaign(
    campaign_id: int,
    payload: CampaignUpdate,
    request: Request,
    session: AsyncSession = Depends(get_session),
    admin=Depends(require_role("admin", "staff")),
) -> CampaignOut:
    campaign = await session.get(Campaign, campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")

    before = CampaignOut.model_validate(campaign)
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(campaign, key, value)
    await session.commit()

    await record_audit(
        session,
        admin_id=admin.id,
        entity="campaigns",
        action="update",
        before=before,
        after=campaign,
        ip=await get_request_ip(request),
        user_agent=request.headers.get("user-agent"),
    )

    return CampaignOut.model_validate(campaign)


@router.delete("/{campaign_id}", response_model=dict)
async def delete_campaign(
    campaign_id: int,
    request: Request,
    session: AsyncSession = Depends(get_session),
    admin=Depends(require_role("admin", "staff")),
) -> dict[str, Any]:
    campaign = await session.get(Campaign, campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")

    before = CampaignOut.model_validate(campaign)
    await session.delete(campaign)
    await session.commit()

    await record_audit(
        session,
        admin_id=admin.id,
        entity="campaigns",
        action="delete",
        before=before,
        after=None,
        ip=await get_request_ip(request),
        user_agent=request.headers.get("user-agent"),
    )

    return {"status": "deleted"}
