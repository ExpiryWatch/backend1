from fastapi import APIRouter, HTTPException

from app.schemas.inventory import (
    InventoryBase,
    InventoryCreate,
    InventoryRead,
    InventoryUpdateResponse,
    InventoryDeleteResponse,
    InventoryErrorResponse,
)

from fastapi import Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import StockItem

router = APIRouter(
    prefix="/inventory",
    tags=["inventory"],
)

@router.get(
    "/",
    response_model=list[InventoryRead],
    summary="Get all inventory items",
    description="Return all inventory items from the database."
)
def get_inventory(db: Session = Depends(get_db)):
    items = db.query(StockItem).all()
    return items

@router.get(
    "/{item_id}",
    response_model=InventoryRead,
    summary="Get inventory item by ID",
    description="Return an inventory item from the database by ID.",
    responses={
        404: {
            "model": InventoryErrorResponse,
            "description": "Inventory item not found"
        }
    }
)
def get_inventory_item(item_id: int, db: Session = Depends(get_db)):
    item = db.get(StockItem, item_id)
    return require_inventory_item(item, item_id)

@router.post(
    "/",
    response_model=InventoryRead,
    status_code=201,
    summary="Create inventory item",
    description="Create a new inventory item in the database."
)
def create_inventory_item(
    item: InventoryCreate,
    db: Session = Depends(get_db)
):
    new_item = StockItem(**item.model_dump())

    db.add(new_item)
    db.commit()
    db.refresh(new_item)

    return new_item

@router.put(
    "/{item_id}",
    response_model=InventoryUpdateResponse,
    summary="Update inventory item",
    description="Accept updated inventory item data by ID. Database updating is not implemented yet."
)
def update_inventory_item(item_id: int, item: InventoryBase):
    return {
        "id": item_id,
        "item": item
    }

@router.delete(
    "/{item_id}",
    response_model=InventoryDeleteResponse,
    summary="Delete inventory item",
    description="Accept inventory item ID for deletion. Database deletion is not implemented yet."
)
def delete_inventory_item(item_id: int):
    return {"id": item_id}

def require_inventory_item(item, item_id: int):
    if item is None:
        raise HTTPException(
            status_code=404,
            detail=f"Inventory item with ID {item_id} not found"
        )
    return item