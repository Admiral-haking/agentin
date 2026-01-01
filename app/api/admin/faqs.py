from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.admin.utils import list_response, parse_filter
from app.api.deps import get_request_ip, require_role
from app.core.database import get_session
from app.models.faq import Faq
from app.schemas.admin.faq import FaqCreate, FaqOut, FaqUpdate
from app.services.audit import record_audit

router = APIRouter(prefix="/admin/faqs", tags=["admin"])


@router.get("", response_model=dict)
async def list_faqs(
    skip: int = 0,
    limit: int = 25,
    sort: str = "created_at",
    order: str = "desc",
    filter: str | None = None,
    session: AsyncSession = Depends(get_session),
    admin=Depends(require_role("admin", "staff")),
) -> dict:
    filters = parse_filter(filter)
    query = select(Faq)
    if "id" in filters:
        ids = filters["id"]
        if isinstance(ids, list):
            query = query.where(Faq.id.in_(ids))
    if "verified" in filters:
        query = query.where(Faq.verified == bool(filters["verified"]))
    if "category" in filters:
        query = query.where(Faq.category == filters["category"])
    if "q" in filters:
        q = f"%{filters['q']}%"
        query = query.where(Faq.question.ilike(q) | Faq.answer.ilike(q))

    sort_col = getattr(Faq, sort, Faq.created_at)
    if order.lower() == "desc":
        query = query.order_by(sort_col.desc())
    else:
        query = query.order_by(sort_col.asc())

    total = await session.scalar(select(func.count()).select_from(query.subquery()))
    result = await session.execute(query.offset(skip).limit(limit))
    items = [FaqOut.model_validate(item) for item in result.scalars().all()]
    return list_response(items, total or 0)


@router.get("/{faq_id}", response_model=FaqOut)
async def get_faq(
    faq_id: int,
    session: AsyncSession = Depends(get_session),
    admin=Depends(require_role("admin", "staff")),
) -> FaqOut:
    faq = await session.get(Faq, faq_id)
    if not faq:
        raise HTTPException(status_code=404, detail="FAQ not found")
    return FaqOut.model_validate(faq)


@router.post("", response_model=FaqOut)
async def create_faq(
    payload: FaqCreate,
    request: Request,
    session: AsyncSession = Depends(get_session),
    admin=Depends(require_role("admin", "staff")),
) -> FaqOut:
    faq = Faq(**payload.model_dump())
    session.add(faq)
    await session.commit()

    await record_audit(
        session,
        admin_id=admin.id,
        entity="faqs",
        action="create",
        before=None,
        after=faq,
        ip=await get_request_ip(request),
        user_agent=request.headers.get("user-agent"),
    )

    return FaqOut.model_validate(faq)


@router.put("/{faq_id}", response_model=FaqOut)
async def update_faq(
    faq_id: int,
    payload: FaqUpdate,
    request: Request,
    session: AsyncSession = Depends(get_session),
    admin=Depends(require_role("admin", "staff")),
) -> FaqOut:
    faq = await session.get(Faq, faq_id)
    if not faq:
        raise HTTPException(status_code=404, detail="FAQ not found")

    before = FaqOut.model_validate(faq)
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(faq, key, value)
    await session.commit()

    await record_audit(
        session,
        admin_id=admin.id,
        entity="faqs",
        action="update",
        before=before,
        after=faq,
        ip=await get_request_ip(request),
        user_agent=request.headers.get("user-agent"),
    )

    return FaqOut.model_validate(faq)


@router.delete("/{faq_id}", response_model=dict)
async def delete_faq(
    faq_id: int,
    request: Request,
    session: AsyncSession = Depends(get_session),
    admin=Depends(require_role("admin", "staff")),
) -> dict[str, Any]:
    faq = await session.get(Faq, faq_id)
    if not faq:
        raise HTTPException(status_code=404, detail="FAQ not found")

    before = FaqOut.model_validate(faq)
    await session.delete(faq)
    await session.commit()

    await record_audit(
        session,
        admin_id=admin.id,
        entity="faqs",
        action="delete",
        before=before,
        after=None,
        ip=await get_request_ip(request),
        user_agent=request.headers.get("user-agent"),
    )

    return {"status": "deleted"}
