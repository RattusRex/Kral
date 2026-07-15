from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.users import get_current_user, get_db
from app.api.projects import get_current_project_access, require_project_admin
from app.models.content import ContentBlock
from app.models.user import User
from app.schemas.content import (
    ContentBlockCreate,
    ContentBlockOrder,
    ContentBlockResponse,
    ContentBlockUpdate,
    HomebrewEntryCreate,
    HomebrewEntryUpdate,
    IllegalItemCreate,
    IllegalItemUpdate,
)


router = APIRouter(prefix="/content-pages", tags=["content pages"])
VALID_PAGE_SLUGS = {"server-rules", "approved-homebrew", "illegal-items"}
STRUCTURED_PAGE_SLUGS = {"approved-homebrew", "illegal-items"}


def validate_page_slug(page_slug: str) -> str:
    if page_slug not in VALID_PAGE_SLUGS:
        raise HTTPException(status_code=404, detail="Content page not found")
    return page_slug


def get_block_or_404(db: Session, project_id: int, page_slug: str, block_id: int) -> ContentBlock:
    block = db.query(ContentBlock).filter(
        ContentBlock.id == block_id,
        ContentBlock.project_id == project_id,
        ContentBlock.page_slug == page_slug,
    ).first()
    if block is None:
        raise HTTPException(status_code=404, detail="Content block not found")
    return block


def ordered_blocks(db: Session, project_id: int, page_slug: str) -> list[ContentBlock]:
    return db.query(ContentBlock).filter(
        ContentBlock.project_id == project_id,
        ContentBlock.page_slug == page_slug,
    ).order_by(
        ContentBlock.position.asc(), ContentBlock.id.asc()
    ).all()


@router.get("/{page_slug}", response_model=list[ContentBlockResponse])
def list_content_blocks(
    page_slug: str,
    db: Session = Depends(get_db),
    access=Depends(get_current_project_access),
):
    return ordered_blocks(db, access[0].id, validate_page_slug(page_slug))


@router.post(
    "/approved-homebrew",
    response_model=ContentBlockResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_homebrew_entry(
    entry_data: HomebrewEntryCreate,
    db: Session = Depends(get_db),
    access=Depends(require_project_admin),
):
    last_position = db.query(func.max(ContentBlock.position)).filter(
        ContentBlock.project_id == access[0].id,
        ContentBlock.page_slug == "approved-homebrew",
    ).scalar()
    values = entry_data.model_dump(mode="json")
    block = ContentBlock(
        project_id=access[0].id,
        page_slug="approved-homebrew",
        content="",
        position=(last_position if last_position is not None else -1) + 1,
        **values,
    )
    db.add(block)
    db.commit()
    db.refresh(block)
    return block


@router.post(
    "/illegal-items",
    response_model=ContentBlockResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_illegal_item(
    item_data: IllegalItemCreate,
    db: Session = Depends(get_db),
    access=Depends(require_project_admin),
):
    last_position = db.query(func.max(ContentBlock.position)).filter(
        ContentBlock.project_id == access[0].id,
        ContentBlock.page_slug == "illegal-items",
    ).scalar()
    block = ContentBlock(
        project_id=access[0].id,
        page_slug="illegal-items",
        content="",
        position=(last_position if last_position is not None else -1) + 1,
        **item_data.model_dump(mode="json"),
    )
    db.add(block)
    db.commit()
    db.refresh(block)
    return block


@router.post(
    "/{page_slug}",
    response_model=ContentBlockResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_content_block(
    page_slug: str,
    block_data: ContentBlockCreate,
    db: Session = Depends(get_db),
    access=Depends(require_project_admin),
):
    page_slug = validate_page_slug(page_slug)
    if page_slug in STRUCTURED_PAGE_SLUGS:
        raise HTTPException(status_code=422, detail="Structured entry required")
    last_position = db.query(func.max(ContentBlock.position)).filter(
        ContentBlock.project_id == access[0].id,
        ContentBlock.page_slug == page_slug,
    ).scalar()
    block = ContentBlock(
        project_id=access[0].id,
        page_slug=page_slug,
        title=block_data.title,
        content=block_data.content,
        position=(last_position if last_position is not None else -1) + 1,
    )
    db.add(block)
    db.commit()
    db.refresh(block)
    return block


@router.put("/{page_slug}/order", response_model=list[ContentBlockResponse])
def reorder_content_blocks(
    page_slug: str,
    order_data: ContentBlockOrder,
    db: Session = Depends(get_db),
    access=Depends(require_project_admin),
):
    page_slug = validate_page_slug(page_slug)
    blocks = ordered_blocks(db, access[0].id, page_slug)
    current_ids = [block.id for block in blocks]
    if len(order_data.block_ids) != len(set(order_data.block_ids)) or set(order_data.block_ids) != set(current_ids):
        raise HTTPException(status_code=400, detail="Order must include every block exactly once")

    blocks_by_id = {block.id: block for block in blocks}
    for temporary_position, block in enumerate(blocks, start=1):
        block.position = -temporary_position
    db.flush()
    for position, block_id in enumerate(order_data.block_ids):
        blocks_by_id[block_id].position = position
    db.commit()
    return ordered_blocks(db, access[0].id, page_slug)


@router.patch("/approved-homebrew/{block_id}", response_model=ContentBlockResponse)
def update_homebrew_entry(
    block_id: int,
    entry_data: HomebrewEntryUpdate,
    db: Session = Depends(get_db),
    access=Depends(require_project_admin),
):
    block = get_block_or_404(db, access[0].id, "approved-homebrew", block_id)
    values = entry_data.model_dump(exclude_unset=True, mode="json")
    for field, value in values.items():
        setattr(block, field, value)
    next_is_banned = block.is_banned
    next_karma_cost = block.karma_cost
    if next_is_banned == (next_karma_cost is not None):
        raise HTTPException(status_code=422, detail="Choose either a karma cost or banned status")
    db.commit()
    db.refresh(block)
    return block


@router.patch("/illegal-items/{block_id}", response_model=ContentBlockResponse)
def update_illegal_item(
    block_id: int,
    item_data: IllegalItemUpdate,
    db: Session = Depends(get_db),
    access=Depends(require_project_admin),
):
    block = get_block_or_404(db, access[0].id, "illegal-items", block_id)
    for field, value in item_data.model_dump(exclude_unset=True, mode="json").items():
        setattr(block, field, value)
    db.commit()
    db.refresh(block)
    return block


@router.patch("/{page_slug}/{block_id}", response_model=ContentBlockResponse)
def update_content_block(
    page_slug: str,
    block_id: int,
    block_data: ContentBlockUpdate,
    db: Session = Depends(get_db),
    access=Depends(require_project_admin),
):
    page_slug = validate_page_slug(page_slug)
    if page_slug in STRUCTURED_PAGE_SLUGS:
        raise HTTPException(status_code=422, detail="Structured entry required")
    block = get_block_or_404(db, access[0].id, page_slug, block_id)
    for field, value in block_data.model_dump(exclude_unset=True).items():
        setattr(block, field, value)
    db.commit()
    db.refresh(block)
    return block


@router.delete("/{page_slug}/{block_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_content_block(
    page_slug: str,
    block_id: int,
    db: Session = Depends(get_db),
    access=Depends(require_project_admin),
):
    page_slug = validate_page_slug(page_slug)
    block = get_block_or_404(db, access[0].id, page_slug, block_id)
    db.delete(block)
    db.flush()
    remaining = ordered_blocks(db, access[0].id, page_slug)
    for position, row in enumerate(remaining):
        row.position = position
    db.commit()
    return None
