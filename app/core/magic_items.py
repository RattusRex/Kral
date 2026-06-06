from functools import lru_cache
import json
from pathlib import Path
from typing import Any


MAGIC_VARIANTS_PATH = Path(__file__).resolve().parents[2] / "magicvariants.json"

RARITY_LABELS = {
    "common": "Обычный",
    "uncommon": "Необычный",
    "rare": "Редкий",
    "very rare": "Очень редкий",
    "legendary": "Легендарный",
    "unknown": "Неизвестная",
    "unknown (magic)": "Неизвестная",
    "none": "Без редкости",
}

RARITY_ORDER = [
    "Обычный",
    "Необычный",
    "Редкий",
    "Очень редкий",
    "Легендарный",
    "Неизвестная",
    "Без редкости",
]

TIER_LABELS = {
    "minor": "Малый",
    "major": "Большой",
}

ARMOR_TYPE_CODES = {"HA", "MA", "LA"}
AMMUNITION_TYPE_CODES = {"A", "AF|DMG"}
WEAPON_REQUIREMENT_KEYS = {
    "axe",
    "bow",
    "crossbow",
    "net",
    "polearm",
    "spear",
    "sword",
    "weapon",
}

TYPE_CODE_LABELS = {
    "A": "боеприпасы",
    "AF|DMG": "боеприпасы",
    "HA": "тяжёлый доспех",
    "LA": "лёгкий доспех",
    "M": "оружие ближнего боя",
    "MA": "средний доспех",
    "S": "щит",
    "SCF": "фокусировка заклинаний",
}

REQUIREMENT_LABELS = {
    "armor": "доспех",
    "arrow": "стрела",
    "axe": "топор",
    "bolt": "арбалетный болт",
    "bow": "лук",
    "crossbow": "арбалет",
    "net": "сеть",
    "polearm": "древковое оружие",
    "spear": "копьё",
    "sword": "меч",
    "weapon": "оружие",
    "weaponCategory": "категория оружия",
}


def normalize_magic_rarity(rarity: str | None) -> str:
    if not rarity:
        return "Неизвестная"
    return RARITY_LABELS.get(rarity.casefold(), rarity)


def _variant_with_inherits(variant: dict[str, Any]) -> dict[str, Any]:
    inherited = variant.get("inherits")
    if not isinstance(inherited, dict):
        inherited = {}
    return {**inherited, **variant}


def _requirements(variant: dict[str, Any]) -> list[dict[str, Any]]:
    requirements = variant.get("requires")
    if not isinstance(requirements, list):
        return []
    return [
        requirement
        for requirement in requirements
        if isinstance(requirement, dict)
    ]


def _has_type(requirements: list[dict[str, Any]], type_codes: set[str]) -> bool:
    return any(requirement.get("type") in type_codes for requirement in requirements)


def _has_requirement_key(
    requirements: list[dict[str, Any]],
    keys: set[str],
) -> bool:
    return any(
        requirement.get(key) is True
        for requirement in requirements
        for key in keys
    )


def _is_consumable(
    variant: dict[str, Any],
    requirements: list[dict[str, Any]],
) -> bool:
    if variant.get("ammo") is True:
        return True
    if _has_type(requirements, AMMUNITION_TYPE_CODES):
        return True
    return _has_requirement_key(requirements, {"arrow", "bolt"})


def _infer_item_type(
    variant: dict[str, Any],
    requirements: list[dict[str, Any]],
) -> str:
    if _is_consumable(variant, requirements):
        return "Боеприпас"
    if any(requirement.get("type") == "S" for requirement in requirements):
        return "Щит"
    if any(requirement.get("armor") is True for requirement in requirements):
        return "Доспех"
    if _has_type(requirements, ARMOR_TYPE_CODES):
        return "Доспех"
    if _has_type(requirements, {"SCF"}):
        return "Фокусировка"
    if _has_requirement_key(requirements, WEAPON_REQUIREMENT_KEYS):
        return "Оружие"
    if _has_type(requirements, {"M"}):
        return "Оружие"
    if variant.get("wondrous") is True:
        return "Чудесный предмет"
    return "Магический предмет"


def _describe_requirement(key: str, value: Any) -> str | None:
    if key == "type":
        return TYPE_CODE_LABELS.get(str(value), f"type: {value}")
    if key == "scfType":
        return f"фокусировка: {value}"
    if key == "name":
        return str(value)
    if key == "source":
        return f"источник: {value}"
    if key == "dmgType":
        return f"тип урона: {value}"
    label = REQUIREMENT_LABELS.get(key, key)
    if value is True:
        return label
    return f"{label}: {value}"


def _describe_requirements(requirements: list[dict[str, Any]]) -> list[str]:
    labels: list[str] = []
    for requirement in requirements:
        for key, value in requirement.items():
            label = _describe_requirement(key, value)
            if label and label not in labels:
                labels.append(label)
    return labels


@lru_cache
def load_magic_items() -> list[dict[str, Any]]:
    with MAGIC_VARIANTS_PATH.open(encoding="utf-8") as variants_file:
        payload = json.load(variants_file)

    variants = payload.get("magicvariant", [])
    if not isinstance(variants, list):
        return []

    items: list[dict[str, Any]] = []
    for index, raw_variant in enumerate(variants):
        if not isinstance(raw_variant, dict):
            continue
        variant = _variant_with_inherits(raw_variant)
        requirements = _requirements(variant)
        raw_rarity = str(variant.get("rarity") or "unknown")
        page = variant.get("page")

        items.append({
            "id": str(index),
            "name": str(variant.get("name") or f"Magic item {index + 1}"),
            "rarity": normalize_magic_rarity(raw_rarity),
            "rarity_key": raw_rarity,
            "item_type": _infer_item_type(variant, requirements),
            "raw_type": str(variant.get("type") or ""),
            "source": str(variant.get("source") or ""),
            "page": page if isinstance(page, int) else None,
            "tier": TIER_LABELS.get(str(variant.get("tier") or ""), None),
            "requires": _describe_requirements(requirements),
            "is_consumable": _is_consumable(variant, requirements),
        })

    return items


def search_magic_items(
    query: str = "",
    rarity: str | None = None,
    item_type: str | None = None,
    limit: int = 80,
) -> list[dict[str, Any]]:
    normalized_query = query.strip().casefold()
    normalized_rarity = rarity.strip() if rarity else None
    normalized_type = item_type.strip() if item_type else None
    bounded_limit = max(1, min(limit, 200))

    matches: list[dict[str, Any]] = []
    for item in load_magic_items():
        if normalized_query and normalized_query not in item["name"].casefold():
            continue
        if normalized_rarity and item["rarity"] != normalized_rarity:
            continue
        if normalized_type and item["item_type"] != normalized_type:
            continue
        matches.append(item)
        if len(matches) >= bounded_limit:
            break

    return matches


def magic_item_filter_options() -> dict[str, list[str]]:
    items = load_magic_items()
    rarity_set = {item["rarity"] for item in items}
    return {
        "rarities": [
            rarity
            for rarity in RARITY_ORDER
            if rarity in rarity_set
        ],
        "item_types": sorted({item["item_type"] for item in items}),
    }
