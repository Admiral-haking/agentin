from __future__ import annotations

from typing import Iterable

STORE_KNOWLEDGE = {
    "name": "فروشگاه قلب دوم",
    "city": "مشهد",
    "website": "ghlbedovom.com",
    "business": "خرده‌فروشی آنلاین و حضوری",
    "categories": [
        "کیف",
        "کفش",
        "پوشاک",
        "عطر",
        "اکسسوری",
        "محصولات آرایشی‌بهداشتی",
    ],
    "strengths": [
        "تضمین اصالت کالا",
        "ارسال سریع به سراسر کشور",
        "پرداخت امن از طریق زرین‌پال",
        "پشتیبانی آنلاین و پاسخ‌گویی ۲۴ ساعته",
    ],
    "branches": [
        {
            "name": "قاسم‌آباد",
            "address": "مشهد، تقاطع شریعتی و فلاحی (فلاحی ۷۳)",
        },
        {
            "name": "سرای حمید",
            "address": "مشهد، بلوار توس، بین توس ۹۴ و ۹۶، سرای حمید، طبقه +1",
        },
        {
            "name": "گلشهر",
            "address": "مشهد، بلوار شهید آوینی",
        },
    ],
    "map_listing": {
        "address": "مشهد، بلوار شریعتی، بین مروارید و بلوار شهید فلاحی (محله شاهد)",
        "hours": "۱۰ تا ۲۳",
        "phone": "09158600035",
        "website": "ghlbedovom.com",
    },
    "trust": {
        "platform": "Torob",
        "store_name": "قلب دوم مارکت",
        "enamad_status": "فعال (۱ ستاره)",
        "enamad_issue_date": "۱۴۰۴/۰۶/۲۱",
        "enamad_expiry": "۱۴۰۶/۰۶/۲۱",
    },
}


def _bulletize(items: Iterable[str]) -> str:
    return "\n".join(f"- {item}" for item in items)


def get_store_knowledge_text() -> str:
    categories = "، ".join(STORE_KNOWLEDGE["categories"])
    strengths = "، ".join(STORE_KNOWLEDGE["strengths"])

    branch_lines = [
        f"{index + 1}) شعبه {branch['name']}: {branch['address']}"
        for index, branch in enumerate(STORE_KNOWLEDGE["branches"])
    ]

    map_listing = STORE_KNOWLEDGE["map_listing"]
    trust = STORE_KNOWLEDGE["trust"]

    lines = [
        f"نام فروشگاه: {STORE_KNOWLEDGE['name']} ({STORE_KNOWLEDGE['city']})",
        f"وب‌سایت: {STORE_KNOWLEDGE['website']}",
        f"نوع فعالیت: {STORE_KNOWLEDGE['business']}",
        f"دسته‌بندی‌ها: {categories}",
        f"مزیت‌ها: {strengths}",
        "شعب:",
        *branch_lines,
        f"آدرس نشان: {map_listing['address']}",
        f"ساعت کاری نشان: {map_listing['hours']}",
        f"تلفن: {map_listing['phone']}",
        (
            f"نماد اعتماد ({trust['platform']} - {trust['store_name']}): "
            f"{trust['enamad_status']} | صدور: {trust['enamad_issue_date']} | "
            f"اعتبار تا: {trust['enamad_expiry']}"
        ),
    ]

    return _bulletize(lines)


def get_branches_text() -> str:
    branch_lines = [
        f"{index + 1}) شعبه {branch['name']}: {branch['address']}"
        for index, branch in enumerate(STORE_KNOWLEDGE["branches"])
    ]
    map_listing = STORE_KNOWLEDGE["map_listing"]
    return "\n".join(
        [
            *branch_lines,
            f"آدرس نشان: {map_listing['address']}",
        ]
    )


def get_hours_text() -> str:
    return f"ساعت کاری طبق نشان: {STORE_KNOWLEDGE['map_listing']['hours']}"


def get_phone_text() -> str:
    return f"شماره تماس: {STORE_KNOWLEDGE['map_listing']['phone']}"


def get_website_url() -> str:
    return f"https://{STORE_KNOWLEDGE['website']}"


def get_trust_text() -> str:
    trust = STORE_KNOWLEDGE["trust"]
    return (
        f"نماد اعتماد فعال (۱ ستاره) برای «{trust['store_name']}» ثبت شده. "
        "پرداخت امن و امکان پیگیری سفارش فراهم است. "
        "پرداخت امن از طریق زرین‌پال و پشتیبانی آنلاین داریم. "
        f"اعتبار نماد تا {trust['enamad_expiry']} است."
    )
