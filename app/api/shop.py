from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.api.users import get_current_user, get_db
from app.models.character import Character
from app.models.inventory import Inventory, InventoryItem
from app.models.user import User
from app.schemas.inventory import GoldUpdateRequest, InventoryResponse, ShopTransactionRequest

router = APIRouter()


def require_positive_amount(amount: int, field_name: str):
    if amount < 0:
        raise HTTPException(
            status_code=400,
            detail=f"{field_name} must not be negative"
        )


def get_character_inventory(
    character_id: int,
    current_user: User,
    db: Session
) -> Inventory:
    character = db.query(Character).filter(
        Character.id == character_id,
        Character.user_id == current_user.id
    ).first()

    if not character:
        raise HTTPException(
            status_code=404,
            detail="Character not found"
        )

    inventory = db.query(Inventory).filter(
        Inventory.character_id == character_id
    ).first()

    if not inventory:
        inventory = Inventory(
            character_id=character_id,
            gold=0
        )
        db.add(inventory)
        db.commit()
        db.refresh(inventory)

    return inventory


@router.get(
    "/characters/{character_id}/inventory",
    response_model=InventoryResponse
)
def get_inventory(
    character_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return get_character_inventory(character_id, current_user, db)


@router.post(
    "/characters/{character_id}/inventory/gold/add",
    response_model=InventoryResponse
)
def add_gold(
    character_id: int,
    gold_data: GoldUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if gold_data.amount <= 0:
        raise HTTPException(
            status_code=400,
            detail="Amount must be positive"
        )

    inventory = get_character_inventory(character_id, current_user, db)
    inventory.gold += gold_data.amount

    db.commit()
    db.refresh(inventory)

    return inventory


@router.post(
    "/characters/{character_id}/shop/buy",
    response_model=InventoryResponse
)
def buy_item(
    character_id: int,
    transaction: ShopTransactionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    require_positive_amount(transaction.item_price, "item_price")
    require_positive_amount(transaction.mercenary_cost, "mercenary_cost")

    total_cost = transaction.item_price + transaction.mercenary_cost
    inventory = get_character_inventory(character_id, current_user, db)

    if inventory.gold < total_cost:
        raise HTTPException(
            status_code=400,
            detail="Not enough gold"
        )

    inventory.gold -= total_cost
    db.add(InventoryItem(
        name=transaction.item_name,
        inventory_id=inventory.id
    ))

    db.commit()
    db.refresh(inventory)

    return inventory


@router.post(
    "/characters/{character_id}/shop/sell",
    response_model=InventoryResponse
)
def sell_item(
    character_id: int,
    transaction: ShopTransactionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    require_positive_amount(transaction.item_price, "item_price")
    require_positive_amount(transaction.mercenary_cost, "mercenary_cost")

    inventory = get_character_inventory(character_id, current_user, db)
    item = db.query(InventoryItem).filter(
        InventoryItem.inventory_id == inventory.id,
        InventoryItem.name == transaction.item_name
    ).first()

    if not item:
        raise HTTPException(
            status_code=400,
            detail="Item is not in inventory"
        )

    if inventory.gold < transaction.mercenary_cost:
        raise HTTPException(
            status_code=400,
            detail="Not enough gold for mercenaries"
        )

    inventory.gold -= transaction.mercenary_cost
    inventory.gold += transaction.item_price
    db.delete(item)

    db.commit()
    db.refresh(inventory)

    return inventory
