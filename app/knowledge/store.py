from __future__ import annotations

from typing import Iterable

STORE_KNOWLEDGE = {
    "name": "فروشگاه قلب دوم",
    "city": "مشهد",
    "website": "ghlbedovom.com",
    "business": "خرده‌فروشی آنلاین و حضوری",
    "about": (
        "قلب دوم مجموعه‌ای از کفش، کیف، پوشاک، عطر، اکسسوری و محصولات آرایشی‌بهداشتی را "
        "با تمرکز بر کیفیت و قیمت مناسب ارائه می‌دهد."
    ),
    "categories": [
        "کیف",
        "کفش",
        "پوشاک",
        "عطر و ادکلن",
        "اکسسوری",
        "محصولات آرایشی‌بهداشتی",
        "شال و روسری",
        "جوراب",
        "لباس زیر",
        "صندل و دمپایی",
        "کلاه و شال گردن",
        "لوازم جانبی",
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
            "map_url": "https://share.google/6ZFD4SSRbFvxRn3G2",
        },
        {
            "name": "سرای حمید",
            "address": "مشهد، بلوار توس، بین توس ۹۴ و ۹۶، سرای حمید، طبقه +1",
            "map_url": "https://share.google/Zn0s1zx07J6IsOV5S",
        },
        {
            "name": "گلشهر",
            "address": "مشهد، بلوار شهید آوینی، شلوغ بازار",
            "map_url": "https://share.google/mZMEepUib3jmZWPkb",
        },
    ],
    "map_listing": {
        "address": "مشهد، تقاطع شریعتی و فلاحی (فلاحی ۷۳)",
        "hours": "۱۰ تا ۲۳ (همه‌روزه)",
        "phone": "09158600035",
        "website": "ghlbedovom.com",
    },
    "trust": {
        "platform": "Enamad",
        "store_name": "قلب دوم",
        "enamad_status": "فعال (۱ ستاره)",
        "enamad_url": "https://trustseal.enamad.ir/?id=427786&Code=g6iRD7dXk2k8WRCXd4bKuwQFdnnDqiNh",
        "torob_url": "https://torob.com/shop/286518/%D9%82%D9%84%D8%A8-%D8%AF%D9%88%D9%85-%D9%85%D8%A7%D8%B1%DA%A9%D8%AA/",
        "zarinpal_url": "https://zarinp.al/ghlbedovom.com",
    },
    "socials": {
        "instagram": "https://www.instagram.com/ghlbedovom",
        "instagram2": "https://www.instagram.com/ghlbedovom2",
        "telegram": "https://t.me/ghlbedovom",
        "whatsapp": "https://wa.me/989918600035",
        "digikala": "https://www.digikala.com/seller/DRFKU/",
    },
    "category_links": [
        {"title": "کفش روزمره", "url": "https://ghlbedovom.com/store/shoes"},
        {"title": "مجلسی و طبی", "url": "https://ghlbedovom.com/store/formal-and-medical"},
        {"title": "صندل و دمپایی", "url": "https://ghlbedovom.com/store/sandals-and-slippers"},
        {"title": "کیف", "url": "https://ghlbedovom.com/store/bag"},
        {"title": "پوشاک", "url": "https://ghlbedovom.com/store/pooshak"},
        {"title": "شال و روسری", "url": "https://ghlbedovom.com/store/shawls-and-scarves"},
        {"title": "لباس زیر", "url": "https://ghlbedovom.com/store/underwear"},
        {"title": "اکسسوری", "url": "https://ghlbedovom.com/store/aksesori"},
        {"title": "آرایشی و بهداشتی", "url": "https://ghlbedovom.com/store/cosmetics"},
        {"title": "عطر و ادکلن", "url": "https://ghlbedovom.com/store/perfume-and-cologne"},
        {"title": "کلاه و شال گردن", "url": "https://ghlbedovom.com/store/hats-and-scarves"},
        {"title": "لوازم جانبی", "url": "https://ghlbedovom.com/store/accessories"},
        {"title": "جوراب", "url": "https://ghlbedovom.com/store/socks"},
        {"title": "سرگرمی", "url": "https://ghlbedovom.com/store/entertainment"},
    ],
}


def _bulletize(items: Iterable[str]) -> str:
    return "\n".join(f"- {item}" for item in items)


def get_store_knowledge_text() -> str:
    categories = "، ".join(STORE_KNOWLEDGE["categories"])
    strengths = "، ".join(STORE_KNOWLEDGE["strengths"])
    about = STORE_KNOWLEDGE.get("about")

    branch_lines = [
        (
            f"{index + 1}) شعبه {branch['name']}: {branch['address']}"
            + (f" | نقشه: {branch['map_url']}" if branch.get("map_url") else "")
        )
        for index, branch in enumerate(STORE_KNOWLEDGE["branches"])
    ]

    map_listing = STORE_KNOWLEDGE["map_listing"]
    trust = STORE_KNOWLEDGE["trust"]
    socials = STORE_KNOWLEDGE.get("socials", {})
    category_links = STORE_KNOWLEDGE.get("category_links", [])
    category_lines = [
        f"{item['title']}: {item['url']}" for item in category_links if item.get("url")
    ]

    lines = [
        f"نام فروشگاه: {STORE_KNOWLEDGE['name']} ({STORE_KNOWLEDGE['city']})",
        f"وب‌سایت: {STORE_KNOWLEDGE['website']}",
        f"نوع فعالیت: {STORE_KNOWLEDGE['business']}",
        f"معرفی کوتاه: {about}" if about else "",
        f"دسته‌بندی‌ها: {categories}",
        f"مزیت‌ها: {strengths}",
        "شعب:",
        *branch_lines,
        f"آدرس نشان: {map_listing['address']}",
        f"ساعت کاری نشان: {map_listing['hours']}",
        f"تلفن: {map_listing['phone']}",
        (
            f"نماد اعتماد ({trust['platform']} - {trust['store_name']}): "
            f"{trust['enamad_status']} | لینک: {trust['enamad_url']}"
        ),
        f"توروب: {trust['torob_url']}",
        f"زرین‌پال: {trust['zarinpal_url']}",
        f"اینستاگرام: {socials.get('instagram')}",
        f"اینستاگرام دوم: {socials.get('instagram2')}",
        f"تلگرام: {socials.get('telegram')}",
        f"واتساپ: {socials.get('whatsapp')}",
        f"دیجی‌کالا: {socials.get('digikala')}",
        "لینک دسته‌ها:",
        *category_lines,
    ]

    return _bulletize([line for line in lines if line])


def get_branches_text() -> str:
    branch_lines = [
        (
            f"{index + 1}) شعبه {branch['name']}: {branch['address']}"
            + (f" | نقشه: {branch['map_url']}" if branch.get("map_url") else "")
        )
        for index, branch in enumerate(STORE_KNOWLEDGE["branches"])
    ]
    map_listing = STORE_KNOWLEDGE["map_listing"]
    return "\n".join(
        [
            *branch_lines,
            f"آدرس نشان: {map_listing['address']}",
        ]
    )


def get_category_links() -> list[dict[str, str]]:
    category_links = STORE_KNOWLEDGE.get("category_links", [])
    return [item for item in category_links if item.get("url")]


def get_hours_text() -> str:
    return f"ساعت کاری همه‌روزه: {STORE_KNOWLEDGE['map_listing']['hours']}"


def get_phone_text() -> str:
    return f"شماره تماس: {STORE_KNOWLEDGE['map_listing']['phone']}"


def get_contact_text(include_website: bool = False) -> str:
    socials = STORE_KNOWLEDGE.get("socials", {})
    parts = [
        f"شماره تماس: {STORE_KNOWLEDGE['map_listing']['phone']}",
        f"واتساپ: {socials.get('whatsapp')}" if socials.get("whatsapp") else "",
        f"اینستاگرام: {socials.get('instagram')}" if socials.get("instagram") else "",
        f"تلگرام: {socials.get('telegram')}" if socials.get("telegram") else "",
    ]
    if include_website:
        parts.append(f"وب‌سایت: https://{STORE_KNOWLEDGE['website']}")
    return "\n".join(part for part in parts if part)


def get_contact_links(include_website: bool = False) -> list[dict[str, str]]:
    socials = STORE_KNOWLEDGE.get("socials", {})
    phone = STORE_KNOWLEDGE["map_listing"].get("phone")
    links = [
        {"title": "تماس تلفنی", "url": f"tel:{phone}"} if phone else {},
        {"title": "واتساپ", "url": socials.get("whatsapp", "")},
        {"title": "اینستاگرام", "url": socials.get("instagram", "")},
        {"title": "اینستاگرام دوم", "url": socials.get("instagram2", "")},
        {"title": "تلگرام", "url": socials.get("telegram", "")},
    ]
    if include_website:
        links.append({"title": "وب‌سایت", "url": f"https://{STORE_KNOWLEDGE['website']}"})
    return [item for item in links if item.get("url")]


def get_branch_cards() -> list[dict[str, str]]:
    cards: list[dict[str, str]] = []
    for branch in STORE_KNOWLEDGE["branches"]:
        cards.append(
            {
                "title": f"شعبه {branch['name']}",
                "subtitle": branch.get("address", ""),
                "url": branch.get("map_url", ""),
            }
        )
    return cards


def get_website_url() -> str:
    return f"https://{STORE_KNOWLEDGE['website']}"


def get_trust_text() -> str:
    trust = STORE_KNOWLEDGE["trust"]
    return (
        f"نماد اعتماد «{trust['store_name']}» فعال است: {trust['enamad_url']}. "
        f"پرداخت امن از طریق زرین‌پال: {trust['zarinpal_url']}. "
        f"صفحه فروشگاه در توروب: {trust['torob_url']}."
    )
