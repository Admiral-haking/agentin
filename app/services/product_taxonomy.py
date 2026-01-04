from __future__ import annotations

from dataclasses import dataclass
import re


_WORD_RE = re.compile(r"[\w\u0600-\u06FF]+", re.UNICODE)
_ARABIC_FIX = str.maketrans({"ي": "ی", "ك": "ک", "‌": " "})


CATEGORY_SYNONYMS: dict[str, set[str]] = {
    "کفش": {
        "کفش",
        "کتونی",
        "اسنیکر",
        "کالج",
        "بوت",
        "نیم بوت",
        "کفش اسپرت",
        "کفش ورزشی",
        "کفش مجلسی",
        "کفش طبی",
        "مجلسی و طبی",
        "kafsh",
        "formal-and-medical",
        "men-shoes",
        "woman-shoes",
        "kids-shoes",
        "sports-shoe",
        "shoe",
        "shoes",
        "sneaker",
        "sneakers",
        "boot",
        "boots",
        "loafer",
        "loafers",
        "sandal",
        "sandals",
        "heel",
        "heels",
    },
    "صندل و دمپایی": {
        "صندل",
        "دمپایی",
        "sandals-and-slippers",
        "slipper",
        "slippers",
        "sandal",
        "sandals",
    },
    "لباس": {
        "لباس",
        "پیراهن",
        "پیراهنی",
        "شومیز",
        "شلوار",
        "شلوارک",
        "تی شرت",
        "تیشرت",
        "تی‌شرت",
        "بلوز",
        "هودی",
        "سویشرت",
        "ژاکت",
        "کاپشن",
        "پالتو",
        "کت",
        "مانتو",
        "روسری",
        "شال",
        "pooshak",
        "lebas",
        "dress",
        "shirt",
        "tshirt",
        "t-shirt",
        "hoodie",
        "sweater",
        "jacket",
        "coat",
        "pants",
        "skirt",
        "top",
        "blouse",
    },
    "شال و روسری": {
        "شال",
        "روسری",
        "اسکارف",
        "shawls-and-scarves",
        "scarf",
        "shawl",
    },
    "لباس زیر": {
        "لباس زیر",
        "زیر",
        "سوتین",
        "شورت",
        "menunderwaer",
        "men-underwear",
        "underwear/menunderwaer",
        "underwear",
        "short",
        "bra",
        "underwear",
        "bra",
        "brief",
    },
    "جوراب": {
        "جوراب",
        "sock",
        "socks",
    },
    "کلاه و شال گردن": {
        "کلاه",
        "شال گردن",
        "گردن",
        "hat",
        "cap",
        "scarf",
    },
    "کیف": {
        "کیف",
        "کوله",
        "کوله پشتی",
        "کیف پول",
        "kif",
        "bag",
        "bags",
        "backpack",
        "wallet",
        "clutch",
        "handbag",
        "sports-bag",
        "evening-bag",
        "auction-bag",
    },
    "زیورآلات": {
        "زیور",
        "زیورآلات",
        "گردنبند",
        "گوشواره",
        "دستبند",
        "انگشتر",
        "jewelry",
        "jewelery",
        "necklace",
        "bracelet",
        "ring",
        "earring",
    },
    "عطر و ادکلن": {
        "عطر",
        "ادکلن",
        "ادکلن",
        "پرفیوم",
        "بادی اسپلش",
        "بادی",
        "اسپری",
        "perfume-and-cologne",
        "body spray",
        "body-spray",
        "body splash",
        "spray",
        "perfume",
        "cologne",
        "fragrance",
        "body-splash",
    },
    "آرایشی و بهداشتی": {
        "آرایشی",
        "بهداشتی",
        "arayeshi",
        "behda",
        "cosmetics",
        "cosmetic",
        "sanitary",
        "makeup",
        "make-up",
    },
    "آرایشی": {
        "آرایشی",
        "رژ",
        "ریمل",
        "کرم",
        "پنکیک",
        "کانسیلر",
        "makeup",
        "cosmetic",
        "lipstick",
        "mascara",
    },
    "بهداشتی": {
        "بهداشتی",
        "شامپو",
        "صابون",
        "لوسیون",
        "مسواک",
        "deodorant",
        "hygiene",
    },
    "اکسسوری": {
        "اکسسوری",
        "لوازم جانبی",
        "کمربند",
        "کلاه",
        "عینک",
        "ساعت",
        "بدلیجات",
        "کش",
        "گیره مو",
        "accessory",
        "accessories",
        "aksesori",
        "watch",
        "belt",
        "hat",
        "cap",
        "glasses",
        "sunglasses",
    },
    "لوازم جانبی کفش": {
        "لوازم جانبی کفش",
        "بند کفش",
        "shoe accessories",
    },
    "سرگرمی": {
        "سرگرمی",
        "پاسور",
        "ویپ",
        "entertainment",
        "game",
    },
}

GENDER_SYNONYMS: dict[str, set[str]] = {
    "مردانه": {
        "مردانه",
        "مردونه",
        "مرد",
        "آقا",
        "آقایان",
        "mardane",
        "men",
        "mens",
        "male",
    },
    "زنانه": {
        "زنانه",
        "زنونه",
        "زن",
        "خانم",
        "بانوان",
        "zanane",
        "women",
        "womens",
        "female",
    },
    "بچگانه": {
        "بچگانه",
        "کودک",
        "نوزاد",
        "bachegane",
        "kid",
        "kids",
        "child",
        "children",
    },
}

STYLE_SYNONYMS: dict[str, set[str]] = {
    "رسمی": {"رسمی", "official", "formal"},
    "اسپرت": {"اسپرت", "sport", "sporty", "casual"},
    "مجلسی": {"مجلسی", "majlesi", "party", "evening"},
    "روزمره": {"روزمره", "روزانه", "rozmare", "roozmare", "daily"},
    "ورزشی": {"ورزشی", "sport", "athletic"},
    "طبی": {"طبی", "medical", "orthopedic"},
}

MATERIAL_SYNONYMS: dict[str, set[str]] = {
    "چرم": {"چرم", "چرمی", "charm", "charmi", "leather"},
    "جیر": {"جیر", "suede"},
    "نخی": {"نخی", "کتان", "پنبه", "cotton", "linen"},
    "فلزی": {"فلزی", "استیل", "steel", "metal"},
    "پلاستیک": {"پلاستیک", "پلاستیکی", "plastic"},
    "پلی‌استر": {"پلی استر", "پلی‌استر", "polyester"},
    "کتان": {"کتان", "linen"},
}

COLOR_KEYWORDS = {
    "مشکی",
    "سفید",
    "قرمز",
    "آبی",
    "سبز",
    "زرد",
    "صورتی",
    "نارنجی",
    "سرمه‌ای",
    "سرمه اي",
    "سرمه",
    "طوسی",
    "خاکستری",
    "کرم",
    "قهوه‌ای",
    "قهوه اي",
    "بنفش",
    "طلایی",
    "طلائي",
    "نقره‌ای",
    "نقره اي",
    "نفتی",
    "لیمویی",
    "زرشکی",
    "آبی نفتی",
    "سبز لجنی",
    "black",
    "white",
    "red",
    "blue",
    "green",
    "yellow",
    "pink",
    "orange",
    "navy",
    "gray",
    "cream",
    "brown",
    "purple",
    "gold",
    "silver",
    "meshki",
    "sefid",
    "ghermez",
    "abi",
    "sabz",
    "zard",
    "sorati",
    "khakestari",
    "tosi",
    "germez",
    "ghahvei",
    "banefsh",
}

SIZE_KEYWORDS = {
    "xs",
    "s",
    "m",
    "l",
    "xl",
    "xxl",
    "xxxl",
    "فری",
    "فری‌سایز",
    "فری سایز",
    "free",
}


@dataclass(frozen=True)
class TagInfo:
    categories: tuple[str, ...]
    genders: tuple[str, ...]
    styles: tuple[str, ...]
    materials: tuple[str, ...]
    colors: tuple[str, ...]
    sizes: tuple[str, ...]


def _normalize_text(text: str | None) -> str:
    if not text:
        return ""
    value = text.translate(_ARABIC_FIX).lower()
    value = value.replace("-", " ").replace("_", " ")
    return " ".join(value.split())


def _match_synonyms(text: str, mapping: dict[str, set[str]]) -> list[str]:
    matches: list[str] = []
    for canonical, keywords in mapping.items():
        if any(keyword in text for keyword in keywords):
            matches.append(canonical)
    return matches


def infer_tags(text: str | None) -> TagInfo:
    normalized = _normalize_text(text)
    if not normalized:
        return TagInfo((), (), (), (), (), ())

    categories = _match_synonyms(normalized, CATEGORY_SYNONYMS)
    genders = _match_synonyms(normalized, GENDER_SYNONYMS)
    styles = _match_synonyms(normalized, STYLE_SYNONYMS)
    materials = _match_synonyms(normalized, MATERIAL_SYNONYMS)
    colors = [color for color in COLOR_KEYWORDS if color in normalized]

    size_matches = re.findall(r"(?:سایز|size)\s*([0-9]{2,3})", normalized)
    sizes = list(size_matches)
    for size in SIZE_KEYWORDS:
        if size in normalized:
            sizes.append(size)
    if sizes and not genders:
        size_numbers = []
        for size in sizes:
            if isinstance(size, str) and size.isdigit():
                size_numbers.append(int(size))
        gender_hints: list[str] = []
        for size in size_numbers:
            if size <= 34:
                gender_hints.append("بچگانه")
            elif size >= 41:
                gender_hints.append("مردانه")
            elif size <= 39:
                gender_hints.append("زنانه")
        if gender_hints:
            genders = list(dict.fromkeys(genders + gender_hints))

    return TagInfo(
        categories=tuple(dict.fromkeys(categories)),
        genders=tuple(dict.fromkeys(genders)),
        styles=tuple(dict.fromkeys(styles)),
        materials=tuple(dict.fromkeys(materials)),
        colors=tuple(dict.fromkeys(colors)),
        sizes=tuple(dict.fromkeys(sizes)),
    )


def expand_query_terms(text: str | None) -> list[str]:
    normalized = _normalize_text(text)
    if not normalized:
        return []
    tokens = [token for token in _WORD_RE.findall(normalized) if len(token) >= 3]
    tags = infer_tags(normalized)
    extras: set[str] = set()
    for category in tags.categories:
        extras.update(CATEGORY_SYNONYMS.get(category, set()))
    for gender in tags.genders:
        extras.update(GENDER_SYNONYMS.get(gender, set()))
    for style in tags.styles:
        extras.update(STYLE_SYNONYMS.get(style, set()))
    for material in tags.materials:
        extras.update(MATERIAL_SYNONYMS.get(material, set()))
    extras.update(tags.colors)
    extras.update(tags.sizes)
    all_terms = list(dict.fromkeys(tokens + [term for term in extras if len(term) >= 3]))
    all_terms.sort(key=len, reverse=True)
    return all_terms
