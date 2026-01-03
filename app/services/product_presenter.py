from __future__ import annotations

from urllib.parse import quote

from app.core.config import settings
from app.models.product import Product
from app.schemas.send import Button, OutboundPlan, TemplateElement

PRODUCT_LIST_KEYWORDS = {
    "محصول",
    "محصولات",
    "لیست",
    "کالا",
    "مدل",
    "نمایش",
    "دیدن",
    "catalog",
    "product",
    "products",
    "list",
}
IMAGE_KEYWORDS = {
    "عکس",
    "تصویر",
    "تصاویر",
    "photo",
    "image",
    "images",
}


def _format_price(value: int | None) -> str:
    if value is None:
        return "نامشخص"
    return f"{value:,}"


def _availability_label(value: str | None) -> str:
    if value == "instock":
        return "موجود"
    if value == "outofstock":
        return "ناموجود"
    return "نامشخص"


def _proxy_image_url(value: str | None) -> str | None:
    if not value:
        return None
    base = settings.MEDIA_PROXY_BASE_URL.strip().rstrip("/")
    if not base:
        return value
    if value.startswith(base):
        return value
    encoded = quote(value, safe="")
    return f"{base}/media-proxy?url={encoded}"


def _normalize_images(value: object | None) -> list[str]:
    if not value:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        return [value.strip()] if value.strip() else []
    return []


def _build_product_buttons(product: Product) -> list[Button]:
    buttons: list[Button] = []
    if product.page_url:
        buttons.append(
            Button(type="web_url", title="مشاهده محصول", url=product.page_url)
        )
    if settings.ORDER_FORM_ENABLED:
        buttons.append(Button(type="postback", title="ثبت سفارش", payload="ثبت سفارش"))
    return buttons[: settings.MAX_BUTTONS]


def wants_product_list(text: str | None) -> bool:
    normalized = (text or "").strip().lower()
    if not normalized:
        return False
    return any(keyword in normalized for keyword in PRODUCT_LIST_KEYWORDS)


def wants_images(text: str | None) -> bool:
    normalized = (text or "").strip().lower()
    if not normalized:
        return False
    return any(keyword in normalized for keyword in IMAGE_KEYWORDS)


def _should_use_carousel(text: str | None, product_count: int) -> bool:
    if product_count <= 1:
        return False
    if not (text or "").strip():
        return True
    return wants_product_list(text)


def build_product_plan(
    text: str | None,
    products: list[Product],
) -> OutboundPlan | None:
    if not products:
        return None

    if _should_use_carousel(text, len(products)):
        elements: list[TemplateElement] = []
        for product in products[: settings.MAX_TEMPLATE_SLIDES]:
            images = _normalize_images(product.images)
            title = product.title or product.slug or "محصول"
            price = _format_price(product.price)
            availability_value = (
                product.availability.value
                if hasattr(product.availability, "value")
                else str(product.availability)
            )
            availability = _availability_label(availability_value)
            subtitle_parts = [f"قیمت: {price}", f"موجودی: {availability}"]
            if product.old_price:
                subtitle_parts.insert(1, f"قبل: {_format_price(product.old_price)}")
            subtitle = " | ".join(subtitle_parts)
            image_url = None
            if images:
                image_url = _proxy_image_url(images[0])
            buttons = _build_product_buttons(product)
            elements.append(
                TemplateElement(
                    title=title[:80],
                    subtitle=subtitle[:80],
                    image_url=image_url,
                    buttons=buttons[: settings.MAX_BUTTONS],
                )
            )
        if elements:
            return OutboundPlan(type="generic_template", elements=elements)

    product = products[0]
    images = _normalize_images(product.images)
    if wants_images(text) and images and len(images) > 1:
        elements: list[TemplateElement] = []
        title = product.title or product.slug or "محصول"
        price = _format_price(product.price)
        availability_value = (
            product.availability.value
            if hasattr(product.availability, "value")
            else str(product.availability)
        )
        availability = _availability_label(availability_value)
        subtitle_parts = [f"قیمت: {price}", f"موجودی: {availability}"]
        if product.old_price:
            subtitle_parts.insert(1, f"قبل: {_format_price(product.old_price)}")
        subtitle = " | ".join(subtitle_parts)
        buttons = _build_product_buttons(product)
        for idx, raw_url in enumerate(
            images[: settings.MAX_TEMPLATE_SLIDES], start=1
        ):
            image_url = _proxy_image_url(raw_url)
            elements.append(
                TemplateElement(
                    title=f"{title} #{idx}"[:80],
                    subtitle=subtitle[:80],
                    image_url=image_url,
                    buttons=buttons[: settings.MAX_BUTTONS],
                )
            )
        if elements:
            return OutboundPlan(type="generic_template", elements=elements)

    if images:
        title = product.title or product.slug or "محصول"
        price = _format_price(product.price)
        availability_value = (
            product.availability.value
            if hasattr(product.availability, "value")
            else str(product.availability)
        )
        availability = _availability_label(availability_value)
        subtitle_parts = [f"قیمت: {price}", f"موجودی: {availability}"]
        if product.old_price:
            subtitle_parts.insert(1, f"قبل: {_format_price(product.old_price)}")
        subtitle = " | ".join(subtitle_parts)
        element = TemplateElement(
            title=title[:80],
            subtitle=subtitle[:80],
            image_url=_proxy_image_url(images[0]),
            buttons=_build_product_buttons(product),
        )
        return OutboundPlan(type="generic_template", elements=[element])

    title = product.title or product.slug or "محصول"
    price = _format_price(product.price)
    availability_value = (
        product.availability.value
        if hasattr(product.availability, "value")
        else str(product.availability)
    )
    availability = _availability_label(availability_value)
    text_parts = [title, f"قیمت: {price}", f"موجودی: {availability}"]
    if product.old_price:
        text_parts.insert(2, f"قبل: {_format_price(product.old_price)}")
    message = " | ".join(text_parts)
    buttons = _build_product_buttons(product)
    return OutboundPlan(type="button", text=message, buttons=buttons)
