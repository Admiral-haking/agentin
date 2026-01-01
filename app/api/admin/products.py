from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.admin.utils import list_response, parse_filter
from app.api.deps import get_request_ip, require_role
from app.core.config import settings
from app.core.database import get_session
from app.models.product import Product
from app.schemas.admin.product import ProductCreate, ProductOut, ProductUpdate
from app.services.audit import record_audit

router = APIRouter(prefix="/admin/products", tags=["admin"])


def _ensure_feature_enabled() -> None:
    if not settings.PRODUCTS_FEATURE_ENABLED:
        raise HTTPException(status_code=404, detail="Products feature disabled")


@router.get("", response_model=dict)
async def list_products(
    skip: int = 0,
    limit: int = 25,
    sort: str = "created_at",
    order: str = "desc",
    filter: str | None = None,
    session: AsyncSession = Depends(get_session),
    admin=Depends(require_role("admin")),
) -> dict:
    _ensure_feature_enabled()
    filters = parse_filter(filter)
    query = select(Product)
    if "id" in filters:
        ids = filters["id"]
        if isinstance(ids, list):
            query = query.where(Product.id.in_(ids))
    if "in_stock" in filters:
        query = query.where(Product.in_stock == bool(filters["in_stock"]))
    if "category" in filters:
        query = query.where(Product.category == filters["category"])
    if "q" in filters:
        q = f"%{filters['q']}%"
        query = query.where(Product.title.ilike(q))

    sort_col = getattr(Product, sort, Product.created_at)
    if order.lower() == "desc":
        query = query.order_by(sort_col.desc())
    else:
        query = query.order_by(sort_col.asc())

    total = await session.scalar(select(func.count()).select_from(query.subquery()))
    result = await session.execute(query.offset(skip).limit(limit))
    items = [ProductOut.model_validate(item) for item in result.scalars().all()]
    return list_response(items, total or 0)


@router.get("/{product_id}", response_model=ProductOut)
async def get_product(
    product_id: int,
    session: AsyncSession = Depends(get_session),
    admin=Depends(require_role("admin")),
) -> ProductOut:
    _ensure_feature_enabled()
    product = await session.get(Product, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return ProductOut.model_validate(product)


@router.post("", response_model=ProductOut)
async def create_product(
    payload: ProductCreate,
    request: Request,
    session: AsyncSession = Depends(get_session),
    admin=Depends(require_role("admin")),
) -> ProductOut:
    _ensure_feature_enabled()
    product = Product(**payload.model_dump())
    session.add(product)
    await session.commit()

    await record_audit(
        session,
        admin_id=admin.id,
        entity="products",
        action="create",
        before=None,
        after=product,
        ip=await get_request_ip(request),
        user_agent=request.headers.get("user-agent"),
    )

    return ProductOut.model_validate(product)


@router.put("/{product_id}", response_model=ProductOut)
async def update_product(
    product_id: int,
    payload: ProductUpdate,
    request: Request,
    session: AsyncSession = Depends(get_session),
    admin=Depends(require_role("admin")),
) -> ProductOut:
    _ensure_feature_enabled()
    product = await session.get(Product, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    before = ProductOut.model_validate(product)
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(product, key, value)
    await session.commit()

    await record_audit(
        session,
        admin_id=admin.id,
        entity="products",
        action="update",
        before=before,
        after=product,
        ip=await get_request_ip(request),
        user_agent=request.headers.get("user-agent"),
    )

    return ProductOut.model_validate(product)


@router.delete("/{product_id}", response_model=dict)
async def delete_product(
    product_id: int,
    request: Request,
    session: AsyncSession = Depends(get_session),
    admin=Depends(require_role("admin")),
) -> dict[str, Any]:
    _ensure_feature_enabled()
    product = await session.get(Product, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    before = ProductOut.model_validate(product)
    await session.delete(product)
    await session.commit()

    await record_audit(
        session,
        admin_id=admin.id,
        entity="products",
        action="delete",
        before=before,
        after=None,
        ip=await get_request_ip(request),
        user_agent=request.headers.get("user-agent"),
    )

    return {"status": "deleted"}
