from __future__ import annotations

from dataclasses import dataclass
import re


_WORD_RE = re.compile(r"[\w\u0600-\u06FF]+", re.UNICODE)
_ARABIC_FIX = str.maketrans({
    "ي": "ی",
    "ك": "ک",
    "‌": " ",
    "۰": "0",
    "۱": "1",
    "۲": "2",
    "۳": "3",
    "۴": "4",
    "۵": "5",
    "۶": "6",
    "۷": "7",
    "۸": "8",
    "۹": "9",
    "٠": "0",
    "١": "1",
    "٢": "2",
    "٣": "3",
    "٤": "4",
    "٥": "5",
    "٦": "6",
    "٧": "7",
    "٨": "8",
    "٩": "9",
})


CATEGORY_SYNONYMS: dict[str, set[str]] = {
    "کفش": {
        "کفش",
        "کف اسپرت",
        "کف اسپورت",
        "کف چرم",
        "کف چرمی",
        "کفش چرم",
        "کفش چرمی",
        "کفش اسپورت",
        "کفش راحتی",
        "کفش روزمره",
        "کفش پیاده روی",
        "کفش پیاده‌روی",
        "پیاده روی",
        "پیاده‌روی",
        "کفش رانینگ",
        "کفش دویدن",
        "کتونی",
        "اسنیکر",
        "اسنیکرز",
        "کالج",
        "بوت",
        "نیم بوت",
        "کفش اسپرت",
        "کفش ورزشی",
        "کفش مجلسی",
        "کفش طبی",
        "مجلسی و طبی",
        "لوفر",
        "موکاسین",
        "kafsh",
        "kafsh sport",
        "sport shoes",
        "sport shoe",
        "walking shoes",
        "running shoes",
        "sneaker shoe",
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
        "دمپایی راحتی",
        "صندل تخت",
        "صندل طبی",
        "صندل زنانه",
        "صندل مردانه",
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
        "ست لباس",
        "لباس مجلسی",
        "لباس راحتی",
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
        "لباس زیر زنانه",
        "لباس زیر مردانه",
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
        "کلاه زمستانی",
        "کلاه بافت",
        "hat",
        "cap",
        "scarf",
    },
    "کیف": {
        "کیف",
        "کوله",
        "کوله پشتی",
        "کیف پول",
        "کیف دستی",
        "کیف دوشی",
        "کیف کمری",
        "کیف مدرسه",
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
        "ادو پرفیوم",
        "ادوپرفیوم",
        "ادو تویلت",
        "ادوتویلت",
        "ادکلن مردانه",
        "ادکلن زنانه",
        "عطر مردانه",
        "عطر زنانه",
        "perfume-and-cologne",
        "body spray",
        "body-spray",
        "body splash",
        "spray",
        "perfume",
        "cologne",
        "fragrance",
        "body-splash",
        "edp",
        "edt",
    },
    "آرایشی و بهداشتی": {
        "آرایشی",
        "بهداشتی",
        "آرایشی بهداشتی",
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
        "رژ لب",
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
        "کرم دست",
        "کرم بدن",
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
        "کفی",
        "shoe accessories",
    },
    "سرگرمی": {
        "سرگرمی",
        "پاسور",
        "ویپ",
        "بازی",
        "گیم",
        "entertainment",
        "game",
    },
}

BRAND_SYNONYMS: dict[str, set[str]] = {
    "Nike": {"nike", "نایک", "نایکی"},
    "Adidas": {"adidas", "آدیداس", "ادیداس"},
    "Puma": {"puma", "پوما"},
    "Reebok": {"reebok", "ریبوک", "ریباک"},
    "New Balance": {"new balance", "newbalance", "نیو بالانس", "نیوبالانس"},
    "Vans": {"vans", "ونس"},
    "Converse": {"converse", "کانورس"},
    "Asics": {"asics", "اسیکس"},
    "Skechers": {"skechers", "اسکیچرز", "اسکچرز", "اسکچر"},
    "Fila": {"fila", "فیلا"},
    "Crocs": {"crocs", "کراکس"},
    "Birkenstock": {"birkenstock", "بیرکن استاک", "بیرکن‌استاک"},
    "Casio": {"casio", "کاسیو"},
    "Ajmal": {"ajmal", "اجمل"},
    "Lattafa": {"lattafa", "لطافه"},
    "Versace": {"versace", "ورساچه"},
    "Chanel": {"chanel", "شنل"},
    "Dior": {"dior", "دیور"},
    "Gucci": {"gucci", "گوچی"},
    "Armani": {"armani", "آرمانی"},
    "Lacoste": {"lacoste", "لاکست"},
    "Zara": {"zara", "زارا"},
    "H&M": {"h&m", "hm", "اچ اند ام"},
    "LC Waikiki": {"lc waikiki", "ال سی وایکیکی", "وایکیکی"},
}

BRAND_CATEGORY_HINTS: dict[str, str] = {
    "Nike": "کفش",
    "Adidas": "کفش",
    "Puma": "کفش",
    "Reebok": "کفش",
    "New Balance": "کفش",
    "Vans": "کفش",
    "Converse": "کفش",
    "Asics": "کفش",
    "Skechers": "کفش",
    "Fila": "کفش",
    "Crocs": "کفش",
    "Birkenstock": "کفش",
    "Ajmal": "عطر و ادکلن",
    "Lattafa": "عطر و ادکلن",
    "Versace": "عطر و ادکلن",
    "Chanel": "عطر و ادکلن",
    "Dior": "عطر و ادکلن",
    "Gucci": "عطر و ادکلن",
    "Armani": "عطر و ادکلن",
    "Casio": "اکسسوری",
    "Zara": "لباس",
    "H&M": "لباس",
    "LC Waikiki": "لباس",
}

GENDER_SYNONYMS: dict[str, set[str]] = {
    "مردانه": {
        "مردانه",
        "مردونه",
        "مرد",
        "آقا",
        "آقایون",
        "آقایان",
        "پسرانه",
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
        "خانوم",
        "خانما",
        "بانوان",
        "دخترانه",
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
    "رسمی": {"رسمی", "اداری", "official", "formal"},
    "اسپرت": {"اسپرت", "اسپورت", "sport", "sporty", "casual"},
    "مجلسی": {"مجلسی", "majlesi", "party", "evening"},
    "روزمره": {"روزمره", "روزانه", "راحتی", "rozmare", "roozmare", "daily"},
    "ورزشی": {"ورزشی", "sport", "athletic", "running", "walking", "trail"},
    "طبی": {"طبی", "medical", "orthopedic"},
}

MATERIAL_SYNONYMS: dict[str, set[str]] = {
    "چرم": {"چرم", "چرمی", "چرم طبیعی", "چرم مصنوعی", "charm", "charmi", "leather", "synthetic", "pu"},
    "جیر": {"جیر", "suede"},
    "نخی": {"نخی", "کتان", "پنبه", "cotton", "linen"},
    "پارچه": {"پارچه", "fabric", "textile"},
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
    "سورمه‌ای",
    "سورمه اي",
    "طوسی",
    "خاکستری",
    "کرم",
    "شیری",
    "نسکافه‌ای",
    "قهوه‌ای",
    "قهوه اي",
    "بنفش",
    "زرشکی",
    "طلایی",
    "طلائي",
    "نقره‌ای",
    "نقره اي",
    "نفتی",
    "لیمویی",
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

_NUMERIC_SIZE_RE = re.compile(r"(?<!\d)([23]\d|4\d|50)(?!\d)")
_CURRENCY_HINTS = ("تومان", "هزار", "میلیون", "ریال")


def _extract_numeric_sizes(normalized: str) -> list[str]:
    sizes: list[str] = []
    for match in _NUMERIC_SIZE_RE.finditer(normalized):
        value = match.group(1)
        window_start = max(0, match.start() - 8)
        window_end = min(len(normalized), match.end() + 8)
        window = normalized[window_start:window_end]
        if any(hint in window for hint in _CURRENCY_HINTS):
            continue
        sizes.append(value)
    return sizes


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


def match_brands(text: str | None) -> list[str]:
    normalized = _normalize_text(text)
    if not normalized:
        return []
    tokens = set(normalized.split())
    matches: list[str] = []
    for brand, keywords in BRAND_SYNONYMS.items():
        for keyword in keywords:
            key = keyword.strip().lower()
            if not key:
                continue
            if " " in key:
                if key in normalized:
                    matches.append(brand)
                    break
            else:
                if key in tokens:
                    matches.append(brand)
                    break
    return matches


def infer_tags(text: str | None) -> TagInfo:
    normalized = _normalize_text(text)
    if not normalized:
        return TagInfo((), (), (), (), (), ())

    tokens = [token for token in _WORD_RE.findall(normalized) if token]
    token_set = set(tokens)

    categories = _match_synonyms(normalized, CATEGORY_SYNONYMS)
    genders = _match_synonyms(normalized, GENDER_SYNONYMS)
    styles = _match_synonyms(normalized, STYLE_SYNONYMS)
    materials = _match_synonyms(normalized, MATERIAL_SYNONYMS)
    colors = [color for color in COLOR_KEYWORDS if color in normalized]
    brands = match_brands(normalized)
    if not categories and brands:
        hinted = [
            BRAND_CATEGORY_HINTS[brand]
            for brand in brands
            if brand in BRAND_CATEGORY_HINTS
        ]
        if hinted:
            categories = list(dict.fromkeys(categories + hinted))

    size_matches = re.findall(r"(?:سایز|size)\s*([0-9]{2,3})", normalized)
    sizes = list(size_matches)
    for size in SIZE_KEYWORDS:
        if " " in size or "‌" in size:
            if size in normalized:
                sizes.append(size)
        elif size in token_set:
            sizes.append(size)
    sizes.extend(_extract_numeric_sizes(normalized))
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
    brands = match_brands(normalized)
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
    for brand in brands:
        extras.add(brand.lower())
        extras.update(BRAND_SYNONYMS.get(brand, set()))
    all_terms = list(dict.fromkeys(tokens + [term for term in extras if len(term) >= 3]))
    all_terms.sort(key=len, reverse=True)
    return all_terms
