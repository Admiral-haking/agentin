from __future__ import annotations

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
            title = product.title or product.slug or "محصول"
            price = _format_price(product.price)
            availability = _availability_label(product.availability.value)
            subtitle_parts = [f"قیمت: {price}", f"موجودی: {availability}"]
            if product.old_price:
                subtitle_parts.insert(1, f"قبل: {_format_price(product.old_price)}")
            subtitle = " | ".join(subtitle_parts)
            image_url = None
            if product.images:
                image_url = product.images[0]
            buttons = []
            if product.page_url:
                buttons.append(
                    Button(type="web_url", title="مشاهده محصول", url=product.page_url)
                )
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
    if wants_images(text) and product.images and len(product.images) > 1:
        elements: list[TemplateElement] = []
        title = product.title or product.slug or "محصول"
        price = _format_price(product.price)
        availability = _availability_label(product.availability.value)
        subtitle_parts = [f"قیمت: {price}", f"موجودی: {availability}"]
        if product.old_price:
            subtitle_parts.insert(1, f"قبل: {_format_price(product.old_price)}")
        subtitle = " | ".join(subtitle_parts)
        buttons = []
        if product.page_url:
            buttons.append(Button(type="web_url", title="مشاهده محصول", url=product.page_url))
        for idx, image_url in enumerate(
            product.images[: settings.MAX_TEMPLATE_SLIDES], start=1
        ):
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

    title = product.title or product.slug or "محصول"
    price = _format_price(product.price)
    availability = _availability_label(product.availability.value)
    text_parts = [title, f"قیمت: {price}", f"موجودی: {availability}"]
    if product.old_price:
        text_parts.insert(2, f"قبل: {_format_price(product.old_price)}")
    message = " | ".join(text_parts)
    buttons = []
    if product.page_url:
        buttons.append(Button(type="web_url", title="مشاهده محصول", url=product.page_url))
    return OutboundPlan(type="button", text=message, buttons=buttons)
