from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.admin.utils import list_response, parse_filter
from app.api.deps import require_role
from app.core.database import get_session
from app.models.user import User
from app.schemas.admin.user import UserImportPayload, UserOut
from app.services.contacts_importer import (
    parse_csv_contacts,
    parse_json_contacts,
    upsert_contacts,
)
from app.services.directam_contacts import (
    DirectamContactsClient,
    DirectamContactsClientError,
    extract_contact_fields,
)

router = APIRouter(prefix="/admin/users", tags=["admin"])


@router.get("", response_model=dict)
async def list_users(
    skip: int = 0,
    limit: int = 25,
    sort: str = "updated_at",
    order: str = "desc",
    filter: str | None = None,
    session: AsyncSession = Depends(get_session),
    admin=Depends(require_role("admin", "staff")),
) -> dict:
    filters = parse_filter(filter)
    query = select(User)

    if "id" in filters:
        ids = filters["id"]
        if isinstance(ids, list):
            query = query.where(User.id.in_(ids))
    if "external_id" in filters:
        query = query.where(User.external_id.ilike(f"%{filters['external_id']}%"))
    if "username" in filters:
        query = query.where(User.username.ilike(f"%{filters['username']}%"))
    if "from" in filters:
        try:
            start = datetime.fromisoformat(filters["from"])
            query = query.where(User.created_at >= start)
        except ValueError:
            pass
    if "to" in filters:
        try:
            end = datetime.fromisoformat(filters["to"])
            query = query.where(User.created_at <= end)
        except ValueError:
            pass

    sort_col = getattr(User, sort, User.updated_at)
    if order.lower() == "desc":
        query = query.order_by(sort_col.desc())
    else:
        query = query.order_by(sort_col.asc())

    total = await session.scalar(select(func.count()).select_from(query.subquery()))
    result = await session.execute(query.offset(skip).limit(limit))
    items = [UserOut.model_validate(item) for item in result.scalars().all()]
    return list_response(items, total or 0)


@router.get("/{user_id}", response_model=UserOut)
async def get_user(
    user_id: int,
    session: AsyncSession = Depends(get_session),
    admin=Depends(require_role("admin", "staff")),
) -> UserOut:
    user = await session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return UserOut.model_validate(user)


@router.post("/sync", response_model=dict)
async def sync_contacts(
    session: AsyncSession = Depends(get_session),
    admin=Depends(require_role("admin")),
) -> dict:
    client = DirectamContactsClient()
    try:
        contacts = await client.fetch_contacts()
    except DirectamContactsClientError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    created = 0
    updated = 0
    skipped = 0

    for contact in contacts:
        external_id, username, follow_status, follower_count = extract_contact_fields(contact)
        if not external_id:
            skipped += 1
            continue

        result = await session.execute(
            select(User).where(User.external_id == external_id)
        )
        user = result.scalars().first()
        if user:
            user.username = username or user.username
            user.follow_status = follow_status or user.follow_status
            if follower_count is not None:
                user.follower_count = follower_count
            user.profile_json = contact
            updated += 1
        else:
            user = User(
                external_id=external_id,
                username=username,
                follow_status=follow_status,
                follower_count=follower_count,
                profile_json=contact,
            )
            session.add(user)
            created += 1

    await session.commit()
    return {"created": created, "updated": updated, "skipped": skipped}


@router.post("/import", response_model=dict)
async def import_contacts(
    payload: UserImportPayload,
    update_existing: bool = True,
    session: AsyncSession = Depends(get_session),
    admin=Depends(require_role("admin")),
) -> dict:
    contacts = [item.model_dump() for item in payload.contacts]
    return await upsert_contacts(
        session, contacts=contacts, update_existing=update_existing
    )


@router.post("/import-csv", response_model=dict)
async def import_contacts_csv(
    file: UploadFile,
    update_existing: bool = True,
    session: AsyncSession = Depends(get_session),
    admin=Depends(require_role("admin")),
) -> dict:
    if file.content_type not in {"text/csv", "application/vnd.ms-excel", "application/octet-stream"}:
        raise HTTPException(status_code=400, detail="CSV file required")

    content = (await file.read()).decode("utf-8", errors="ignore")
    contacts = parse_csv_contacts(content)
    if not contacts:
        raise HTTPException(status_code=400, detail="CSV headers are missing")
    return await upsert_contacts(
        session, contacts=contacts, update_existing=update_existing
    )


@router.post("/import-json", response_model=dict)
async def import_contacts_json(
    file: UploadFile,
    update_existing: bool = True,
    session: AsyncSession = Depends(get_session),
    admin=Depends(require_role("admin")),
) -> dict:
    if file.content_type not in {"application/json", "text/plain", "application/octet-stream"}:
        raise HTTPException(status_code=400, detail="JSON file required")

    content = (await file.read()).decode("utf-8", errors="ignore")
    contacts = parse_json_contacts(content)
    if not contacts:
        raise HTTPException(status_code=400, detail="JSON did not contain contacts")
    return await upsert_contacts(
        session, contacts=contacts, update_existing=update_existing
    )
