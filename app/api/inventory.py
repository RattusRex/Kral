from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.database import SessionLocal
from app.models.character import Character
from app.models.inventory import Inventory, InventoryItem
from app.models.user import User
from app.api.users import get_current_user
from app.schemas.inventory import (
    AddItemRequest,
    CurrencyUpdateRequest,
    GoldUpdateRequest,
    InventoryResponse,
    ShopBuyRequest,
    ShopResult,
    ShopSearchRequest,
    ShopSellRequest,
)
import random


router = APIRouter()

RARITY_DATA = {
    "Обычный": {"dc": 5, "days_dice": 4, "base_price": 100},
    "Необычный": {"dc": 10, "days_dice": 8, "base_price": 500},
    "Редкий": {"dc": 15, "days_dice": 12, "base_price": 5000},
}

CONSUMABLE_BASE_PRICE = {
    "Обычный": 50,
    "Необычный": 250,
    "Редкий": 2500,
}

RARITY_PRICE_ROLL_MODIFIER = {
    "Обычный": 10,
    "Необычный": 0,
    "Редкий": -10,
}

HIRELING_BONUSES = {
    "Плохой": 0,
    "Хороший": 4,
    "Опытный": 6,
    "Экспертный": 8,
}

HIRELING_DAILY_COST = {
    "Плохой": 1,
    "Хороший": 5,
    "Опытный": 10,
    "Экспертный": 25,
}
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


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
            gold=0,
            silver=0,
            copper=0
        )
        db.add(inventory)
        db.commit()
        db.refresh(inventory)

    return inventory

def validate_rarity(rarity: str):
    if rarity not in RARITY_DATA:
        raise HTTPException(
            status_code=400,
            detail="Unknown rarity"
        )
def require_non_negative_currency(currency: CurrencyUpdateRequest):
    if currency.gold < 0 or currency.silver < 0 or currency.copper < 0:
        raise HTTPException(
            status_code=400,
            detail="Currency amounts must not be negative"
        )
def inventory_total_copper(inventory: Inventory) -> int:
    return inventory.gold * 100 + inventory.silver * 10 + inventory.copper

def set_inventory_from_copper(inventory: Inventory, amount: int):
    inventory.gold = amount // 100
    amount %= 100
    inventory.silver = amount // 10
    inventory.copper = amount % 10

def add_currency(inventory: Inventory, gold: int = 0, silver: int = 0, copper: int = 0):
    set_inventory_from_copper(
        inventory,
        inventory_total_copper(inventory) + gold * 100 + silver * 10 + copper
    )

def subtract_copper(inventory: Inventory, amount: int, detail: str):
    current_amount = inventory_total_copper(inventory)
    if current_amount < amount:
        raise HTTPException(
            status_code=400,
            detail=detail
        )
    set_inventory_from_copper(inventory, current_amount - amount)

def base_price_for_item(rarity: str, is_consumable: bool) -> int:
    validate_rarity(rarity)
    if is_consumable:
        return CONSUMABLE_BASE_PRICE[rarity]
    return RARITY_DATA[rarity]["base_price"]

def adjusted_price_roll(rarity: str) -> int:
    price_roll = random.randint(1, 100) + RARITY_PRICE_ROLL_MODIFIER[rarity]
    return max(1, min(100, price_roll))

def roll_buy_price_multiplier(rarity: str):
    price_roll = adjusted_price_roll(rarity)
    if price_roll <= 20:
        multiplier = 1.5 + (random.randint(0, 500) / 1000)
    elif price_roll <= 40:
        multiplier = 1.0 + (random.randint(0, 490) / 1000)
    elif price_roll <= 80:
        multiplier = 0.75 + (random.randint(0, 240) / 1000)
    elif price_roll <= 90:
        multiplier = 0.5 + (random.randint(0, 240) / 1000)
    else:
        multiplier = 0.5 - (random.randint(0, 200) / 1000)
    return price_roll, multiplier


def roll_sell_price_multiplier(rarity: str):
    price_roll = adjusted_price_roll(rarity)
    if price_roll <= 20:
        multiplier = 0.5 - (random.randint(0, 200) / 1000)
    elif price_roll <= 42:
        multiplier = 0.5 + (random.randint(0, 250) / 1000)
    elif price_roll <= 82:
        multiplier = 0.75 + (random.randint(0, 150) / 1000)
    elif price_roll <= 92:
        multiplier = 0.9 + (random.randint(0, 350) / 1000)
    else:
        multiplier = 1.25 + (random.randint(0, 350) / 1000)
    return price_roll, multiplier

def search_item(character: Character, request: ShopSearchRequest):
    validate_rarity(request.rarity)
    rarity_data = RARITY_DATA[request.rarity]

    if request.searcher_type == "character":
        modifier = character.investigation
        daily_cost = 0
    elif request.searcher_type == "hireling":
        if request.hireling_level not in HIRELING_BONUSES:
            raise HTTPException(
                status_code=400,
                detail="Unknown hireling level"
            )
        modifier = HIRELING_BONUSES[request.hireling_level]
        daily_cost = HIRELING_DAILY_COST[request.hireling_level]
    else:
        raise HTTPException(
            status_code=400,
            detail="Unknown searcher type"
        )

    search_roll = random.randint(1, 20)
    total_roll = search_roll + modifier
    success = total_roll >= rarity_data["dc"]
    if success:
        days = random.randint(1, rarity_data["days_dice"])
    else:
        days = rarity_data["days_dice"]

    return {
        "success": success,
        "search_roll": search_roll,
        "modifier": modifier,
        "total_roll": total_roll,
        "dc": rarity_data["dc"],
        "days": days,
        "hireling_cost": days * daily_cost
    }

@router.get("/characters/{character_id}/inventory", response_model=InventoryResponse)
def get_inventory(
    character_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    inventory = get_character_inventory(character_id, current_user, db)
    return inventory


@router.post("/characters/{character_id}/inventory/items", response_model=InventoryResponse)
def add_item(
    character_id: int,
    item_data: AddItemRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    validate_rarity(item_data.rarity)
    inventory = get_character_inventory(character_id, current_user, db)

    item = InventoryItem(
        name=item_data.name,
        rarity=item_data.rarity,
        is_consumable=item_data.is_consumable,
        inventory_id=inventory.id
    )
    db.add(item)
    db.commit()
    db.refresh(inventory)

    return inventory


@router.delete("/characters/{character_id}/inventory/items/{item_id}", response_model=InventoryResponse)
def remove_item(
    character_id: int,
    item_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    inventory = get_character_inventory(character_id, current_user, db)

    item = db.query(InventoryItem).filter(
        InventoryItem.id == item_id,
        InventoryItem.inventory_id == inventory.id
    ).first()

    if not item:
        raise HTTPException(
            status_code=404,
            detail="Предмет не найден"
        )

    db.delete(item)
    db.commit()
    db.refresh(inventory)

    return inventory


@router.post("/characters/{character_id}/inventory/gold/add", response_model=InventoryResponse)
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


@router.post("/characters/{character_id}/inventory/gold/subtract", response_model=InventoryResponse)
def subtract_gold(
    character_id: int,
    gold_data: GoldUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if gold_data.amount <= 0:
        raise HTTPException(
            status_code=400,
            detail="Число должно быть положительным"
        )

    inventory = get_character_inventory(character_id, current_user, db)

    if inventory.gold < gold_data.amount:
        raise HTTPException(
            status_code=400,
            detail="Недостаточно денег"
        )

    inventory.gold -= gold_data.amount
    db.commit()
    db.refresh(inventory)

    return inventory

@router.post("/characters/{character_id}/inventory/currency/add", response_model=InventoryResponse)
def add_inventory_currency(
    character_id: int,
    currency_data: CurrencyUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    require_non_negative_currency(currency_data)
    inventory = get_character_inventory(character_id, current_user, db)
    add_currency(
        inventory,
        currency_data.gold,
        currency_data.silver,
        currency_data.copper
    )
    db.commit()
    db.refresh(inventory)

    return inventory

@router.post("/characters/{character_id}/shop/search", response_model=ShopResult)
def search_shop_item(
    character_id: int,
    search_data: ShopSearchRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    character = db.query(Character).filter(
        Character.id == character_id,
        Character.user_id == current_user.id
    ).first()

    if not character:
        raise HTTPException(
            status_code=404,
            detail="Персонаж не найден"
        )

    inventory = get_character_inventory(character_id, current_user, db)
    search_result = search_item(character, search_data)
    subtract_copper(
        inventory,
        search_result["hireling_cost"],
        "Недостаточно денег для наёмников"
    )
    db.commit()
    db.refresh(inventory)

    return {
        **search_result,
        "price_roll": None,
        "multiplier": None,
        "item_price": None,
        "total_cost": search_result["hireling_cost"],
        "inventory": inventory
    }

@router.post("/characters/{character_id}/shop/buy", response_model=ShopResult)
def buy_shop_item(
    character_id: int,
    buy_data: ShopBuyRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    character = db.query(Character).filter(
        Character.id == character_id,
        Character.user_id == current_user.id
    ).first()

    if not character:
        raise HTTPException(
            status_code=404,
            detail="Персонаж не найден"
        )

    inventory = get_character_inventory(character_id, current_user, db)
    search_result = search_item(character, buy_data)
    if not search_result["success"]:
        subtract_copper(
            inventory,
            search_result["hireling_cost"],
            "Недостаточно денег для наёмников"
        )
        db.commit()
        db.refresh(inventory)
        return {
            **search_result,
            "price_roll": None,
            "multiplier": None,
            "item_price": None,
            "total_cost": search_result["hireling_cost"],
            "inventory": inventory
        }

    price_roll, multiplier = roll_buy_price_multiplier(buy_data.rarity)
    item_price = round(base_price_for_item(
        buy_data.rarity,
        buy_data.is_consumable
    ) * multiplier)
    total_cost = item_price + search_result["hireling_cost"]
    subtract_copper(inventory, total_cost, "Недостаточно денег")
    db.add(InventoryItem(
        name=buy_data.item_name,
        rarity=buy_data.rarity,
        is_consumable=buy_data.is_consumable,
        inventory_id=inventory.id
    ))
    db.commit()
    db.refresh(inventory)

    return {
        **search_result,
        "price_roll": price_roll,
        "multiplier": multiplier,
        "item_price": item_price,
        "total_cost": total_cost,
        "inventory": inventory
    }

@router.post("/characters/{character_id}/shop/sell", response_model=ShopResult)
def sell_shop_item(
    character_id: int,
    sell_data: ShopSellRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    character = db.query(Character).filter(
        Character.id == character_id,
        Character.user_id == current_user.id
    ).first()

    if not character:
        raise HTTPException(
            status_code=404,
            detail="Персонаж не найден"
        )

    inventory = get_character_inventory(character_id, current_user, db)
    item = db.query(InventoryItem).filter(
        InventoryItem.id == sell_data.item_id,
        InventoryItem.inventory_id == inventory.id
    ).first()

    if not item:
        raise HTTPException(
            status_code=400,
            detail="Предмета нет в инвентаре"
        )

    search_data = ShopSearchRequest(
        item_name=item.name,
        rarity=item.rarity,
        is_consumable=item.is_consumable,
        searcher_type=sell_data.searcher_type,
        hireling_level=sell_data.hireling_level
    )
    search_result = search_item(character, search_data)
    subtract_copper(
        inventory,
        search_result["hireling_cost"],
        "Недостаточно денег для наёмников"
    )

    price_roll = None
    multiplier = None
    item_price = None
    if search_result["success"]:
        price_roll, multiplier = roll_sell_price_multiplier(item.rarity)
        item_price = round(base_price_for_item(
            item.rarity,
            item.is_consumable
        ) * multiplier)
        add_currency(inventory, copper=item_price)
        db.delete(item)

    db.commit()
    db.refresh(inventory)


    return {
        **search_result,
        "price_roll": price_roll,
        "multiplier": multiplier,
        "item_price": item_price,
        "total_cost": search_result["hireling_cost"],
        "inventory": inventory
    }