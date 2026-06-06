from fastapi import APIRouter, Depends, Query

from app.api.users import get_current_user
from app.core.magic_items import magic_item_filter_options, search_magic_items
from app.models.user import User
from app.schemas.magic_items import MagicItemFilterOptions, MagicItemResponse


router = APIRouter()


@router.get("/magic-items", response_model=list[MagicItemResponse])
def list_magic_items(
    q: str = "",
    rarity: str | None = None,
    item_type: str | None = None,
    limit: int = Query(80, ge=1, le=200),
    _: User = Depends(get_current_user),
):
    return search_magic_items(
        query=q,
        rarity=rarity,
        item_type=item_type,
        limit=limit,
    )


@router.get("/magic-items/options", response_model=MagicItemFilterOptions)
def get_magic_item_options(
    _: User = Depends(get_current_user),
):
    return magic_item_filter_options()
