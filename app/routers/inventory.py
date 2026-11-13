from fastapi import APIRouter, HTTPException

from app.schemas.inventory import (
    InventoryBase,
    InventoryUpdateResponse,
    InventoryDeleteResponse,
    InventoryErrorResponse,
)

router = APIRouter(
    prefix="/inventory",
    tags=["inventory"],
)

@router.get(
    "/",
    response_model=list[InventoryBase],
    summary="Get all inventory items",
    description="Return a list of inventory items. Database retrieval is not implemented yet."
)
def get_inventory():
    return []

@router.get(
    "/{item_id}",
    response_model=InventoryBase,
    summary="Get inventory item by ID",
    description="Return an inventory item by ID. Database lookup is not implemented yet.",
    responses={
        404: {
            "model": InventoryErrorResponse,
            "description": "Inventory item not found"
        }
    }
)
def get_inventory_item(item_id: int):
    item = None

    return require_inventory_item(item, item_id)

@router.post(
    "/",
    response_model=InventoryBase,
    summary="Create inventory item",
    description="Accept inventory item data. Database saving is not implemented yet."
)
def create_inventory_item(item: InventoryBase):
    return item

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