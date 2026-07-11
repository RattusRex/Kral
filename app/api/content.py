from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.users import get_current_user, get_db
from app.models.content import ContentBlock
from app.models.user import User
from app.schemas.content import (
    ContentBlockCreate,
    ContentBlockOrder,
    ContentBlockResponse,
    ContentBlockUpdate,
)


router = APIRouter(prefix="/content-pages", tags=["content pages"])
VALID_PAGE_SLUGS = {"server-rules", "approved-homebrew"}


def validate_page_slug(page_slug: str) -> str:
    if page_slug not in VALID_PAGE_SLUGS:
        raise HTTPException(status_code=404, detail="Content page not found")
    return page_slug


def require_admin(current_user: User = Depends(get_current_user)) -> User:
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin permissions required")
    return current_user


def get_block_or_404(db: Session, page_slug: str, block_id: int) -> ContentBlock:
    block = db.query(ContentBlock).filter(
        ContentBlock.id == block_id,
        ContentBlock.page_slug == page_slug,
    ).first()
    if block is None:
        raise HTTPException(status_code=404, detail="Content block not found")
    return block


def ordered_blocks(db: Session, page_slug: str) -> list[ContentBlock]:
    return db.query(ContentBlock).filter(ContentBlock.page_slug == page_slug).order_by(
        ContentBlock.position.asc(), ContentBlock.id.asc()
    ).all()


@router.get("/{page_slug}", response_model=list[ContentBlockResponse])
def list_content_blocks(
    page_slug: str,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    return ordered_blocks(db, validate_page_slug(page_slug))


@router.post(
    "/{page_slug}",
    response_model=ContentBlockResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_content_block(
    page_slug: str,
    block_data: ContentBlockCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    page_slug = validate_page_slug(page_slug)
    last_position = db.query(func.max(ContentBlock.position)).filter(
        ContentBlock.page_slug == page_slug
    ).scalar()
    block = ContentBlock(
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
    _: User = Depends(require_admin),
):
    page_slug = validate_page_slug(page_slug)
    blocks = ordered_blocks(db, page_slug)
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
    return ordered_blocks(db, page_slug)


@router.patch("/{page_slug}/{block_id}", response_model=ContentBlockResponse)
def update_content_block(
    page_slug: str,
    block_id: int,
    block_data: ContentBlockUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    block = get_block_or_404(db, validate_page_slug(page_slug), block_id)
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
    _: User = Depends(require_admin),
):
    page_slug = validate_page_slug(page_slug)
    block = get_block_or_404(db, page_slug, block_id)
    db.delete(block)
    db.flush()
    remaining = ordered_blocks(db, page_slug)
    for position, row in enumerate(remaining):
        row.position = position
    db.commit()
    return None
