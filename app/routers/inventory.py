from fastapi import APIRouter, HTTPException, Depends, Query

from app.schemas.inventory import (
    InventoryBase,
    InventoryCreate,
    InventoryRead,
    InventoryUpdateResponse,
    InventoryDeleteResponse,
    InventoryErrorResponse,
)


from sqlalchemy.orm import Session

from app.database import get_db
from app.models import StockItem

from typing import Literal

from app.queries import list_items
from app.models import ExpiryStatus

router = APIRouter(
    prefix="/inventory",
    tags=["inventory"],
)

@router.get(
    "/",
    response_model=list[InventoryRead],
    summary="Get all inventory items",
    description="Return inventory items with search, filters and sorting."
)
def get_inventory(
    db: Session = Depends(get_db),
    q: str | None = None,
    category_id: int | None = None,
    storage_location_id: int | None = None,
    status: ExpiryStatus | None = None,
    sort: Literal["name", "expiry"] = "name",
    order: Literal["asc", "desc"] = "asc",
    limit: int | None = Query(default=None, ge=1),
    offset: int = Query(default=0, ge=0)
):
    items = list_items(
        db,
        q=q,
        category_id=category_id,
        storage_location_id=storage_location_id,
        status=status,
        sort=sort,
        order=order,
        limit=limit,
        offset=offset
    )

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
    response_model=InventoryRead,
    summary="Update inventory item",
    description="Update an existing inventory item in the database.",
    responses={
        404: {
            "model": InventoryErrorResponse,
            "description": "Inventory item not found"
        }
    }
)
def update_inventory_item(
    item_id: int,
    item: InventoryCreate,
    db: Session = Depends(get_db)
):
    existing_item = db.get(StockItem, item_id)

    require_inventory_item(existing_item, item_id)

    data = item.model_dump()

    for field, value in data.items():
        setattr(existing_item, field, value)

    db.commit()
    db.refresh(existing_item)

    return existing_item

@router.delete(
    "/{item_id}",
    response_model=InventoryDeleteResponse,
    summary="Delete inventory item",
    description="Delete an inventory item from the database.",
    responses={
        404: {
            "model": InventoryErrorResponse,
            "description": "Inventory item not found"
        }
    }
)
def delete_inventory_item(
    item_id: int,
    db: Session = Depends(get_db)
):
    item = db.get(StockItem, item_id)

    require_inventory_item(item, item_id)

    db.delete(item)
    db.commit()

    return {"id": item_id}

def require_inventory_item(item, item_id: int):
    if item is None:
        raise HTTPException(
            status_code=404,
            detail=f"Inventory item with ID {item_id} not found"
        )
    return item