import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, Query

from app.api.users import get_current_user
from app.models.user import User
from app.schemas.inventory import MagicItemResponse


router = APIRouter()

MAGIC_VARIANTS_PATH = Path(__file__).resolve().parents[2] / "magicvariants.json"

RARITY_LABELS = {
    "common": "Обычный",
    "uncommon": "Необычный",
    "rare": "Редкий",
    "very rare": "Очень редкий",
    "legendary": "Легендарный",
    "artifact": "Артефакт",
    "unknown": "Неизвестная",
    "unknown (magic)": "Неизвестная магическая",
    "none": "Без редкости",
}

TAG_PATTERN = re.compile(r"\{@[a-zA-Z]+ ([^}|]+)(?:\|[^}]*)?\}")
INLINE_VALUE_PATTERN = re.compile(r"\{=([^}]+)\}")
ITEM_ENTRY_PATTERN = re.compile(r"\{#itemEntry ([^}]+)\}")


def scalar_value(value: Any) -> str | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float, str)):
        return str(value)
    return None


def render_text(text: str, values: dict[str, Any]) -> str:
    for key, value in values.items():
        replacement = scalar_value(value)
        if replacement is not None:
            text = text.replace(f"{{={key}}}", replacement)
    text = ITEM_ENTRY_PATTERN.sub(r"\1", text)
    text = TAG_PATTERN.sub(r"\1", text)
    text = INLINE_VALUE_PATTERN.sub(r"\1", text)
    return " ".join(text.split())


def collect_text(value: Any, values: dict[str, Any]) -> list[str]:
    if isinstance(value, str):
        return [render_text(value, values)]
    if isinstance(value, list):
        chunks: list[str] = []
        for entry in value:
            chunks.extend(collect_text(entry, values))
        return chunks
    if isinstance(value, dict):
        if "entries" in value:
            prefix = value.get("name")
            chunks = collect_text(value["entries"], values)
            if isinstance(prefix, str) and chunks:
                chunks[0] = f"{prefix}. {chunks[0]}"
            return chunks
        if "items" in value:
            return collect_text(value["items"], values)
        if "name" in value:
            return [render_text(str(value["name"]), values)]
    return []


def requirement_type(item: dict[str, Any], merged: dict[str, Any]) -> str:
    if item.get("ammo") or merged.get("ammo"):
        return "Боеприпас"

    for requirement in item.get("requires", []):
        if not isinstance(requirement, dict):
            continue
        if requirement.get("armor"):
            return "Доспех"
        if requirement.get("weapon"):
            return "Оружие"
        type_code = str(requirement.get("type", ""))
        if type_code == "S":
            return "Щит"
        if type_code in {"A", "AF|DMG"}:
            return "Боеприпас"

    if merged.get("wondrous"):
        return "Чудесный предмет"
    return "Вариант предмета"


def normalize_rarity(raw_rarity: str | None) -> str:
    normalized = (raw_rarity or "unknown").strip().lower()
    return RARITY_LABELS.get(normalized, normalized.capitalize())


def normalize_magic_item(index: int, item: dict[str, Any]) -> dict[str, Any]:
    inherits = item.get("inherits") if isinstance(item.get("inherits"), dict) else {}
    merged = {**inherits, **item}
    raw_rarity = str(merged.get("rarity") or "unknown")
    req_attune = merged.get("reqAttune", False)
    entries = [
        *collect_text(item.get("entries", []), merged),
        *collect_text(inherits.get("entries", []), merged),
    ]
    description = " ".join(entry for entry in entries if entry)

    return {
        "id": index,
        "name": str(item.get("name", "")).strip(),
        "rarity": normalize_rarity(raw_rarity),
        "raw_rarity": raw_rarity,
        "type": requirement_type(item, merged),
        "source": scalar_value(merged.get("source")),
        "page": merged.get("page") if isinstance(merged.get("page"), int) else None,
        "tier": scalar_value(merged.get("tier")),
        "requires_attunement": bool(req_attune),
        "attunement_note": req_attune if isinstance(req_attune, str) else None,
        "is_consumable": bool(item.get("ammo") or merged.get("ammo")),
        "description": description,
    }


@lru_cache
def load_magic_items() -> tuple[dict[str, Any], ...]:
    with MAGIC_VARIANTS_PATH.open(encoding="utf-8") as file:
        data = json.load(file)

    variants = data.get("magicvariant", [])
    if not isinstance(variants, list):
        return tuple()

    items = [
        normalize_magic_item(index + 1, item)
        for index, item in enumerate(variants)
        if isinstance(item, dict) and str(item.get("name", "")).strip()
    ]
    return tuple(sorted(items, key=lambda magic_item: magic_item["name"].lower()))


@router.get("/shop/magic-items", response_model=list[MagicItemResponse])
def get_magic_items(
    q: str | None = Query(default=None),
    rarity: str | None = Query(default=None),
    type: str | None = Query(default=None),
    limit: int = Query(default=1000, ge=1, le=1000),
    current_user: User = Depends(get_current_user),
):
    del current_user
    query = (q or "").strip().lower()
    rarity_filter = (rarity or "").strip()
    type_filter = (type or "").strip()
    matches = []

    for item in load_magic_items():
        if query and query not in item["name"].lower():
            continue
        if rarity_filter and item["rarity"] != rarity_filter:
            continue
        if type_filter and item["type"] != type_filter:
            continue
        matches.append(item)
        if len(matches) >= limit:
            break

    return matches
