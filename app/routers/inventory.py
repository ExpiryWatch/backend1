from fastapi import APIRouter, HTTPException, Depends, Query
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError

from app.schemas.inventory import (
    InventoryCreate,
    InventoryPatch,
    InventoryPut,
    InventoryRead,
    InventoryDeleteResponse,
    InventoryErrorResponse,
)


from sqlalchemy.orm import Session

from app.database import get_db
from app.models import StockItem, Category, StorageLocation

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
    description="Return inventory items with search, filters and sorting.",
    responses={
        422: {
            "model": InventoryErrorResponse,
            "description": "Invalid search, filter or pagination parameters"
        }
    }
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
        },
        422: {
            "model": InventoryErrorResponse,
            "description": "Invalid inventory item ID"
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
    description="Create a new inventory item in the database.",
    responses={
        422: {
            "model": InventoryErrorResponse,
            "description": "Invalid input data, category or storage location"
        }
    }
)
def create_inventory_item(
    item: InventoryCreate,
    db: Session = Depends(get_db)
):
    if item.category_id is not None:
        category = db.get(Category, item.category_id)

        if category is None:
            raise HTTPException(
                status_code=422,
                detail=f"Категория с ID {item.category_id} не найдена"
            )
    if item.storage_location_id is not None:
        location = db.get(StorageLocation, item.storage_location_id)

        if location is None:
            raise HTTPException(
                status_code=422,
                detail=f"Место хранения с ID {item.storage_location_id} не найдено"
            )
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
        },
        422: {
            "model": InventoryErrorResponse,
            "description": "Invalid input data, category or storage location"
        }
    }
)
def update_inventory_item(
    item_id: int,
    item: InventoryPut,
    db: Session = Depends(get_db)
):
    existing_item = db.get(StockItem, item_id)

    require_inventory_item(existing_item, item_id)

    if item.category_id is not None:
        category = db.get(Category, item.category_id)

        if category is None:
            raise HTTPException(
                status_code=422,
                detail=f"Категория с ID {item.category_id} не найдена"
            )

    if item.storage_location_id is not None:
        location = db.get(StorageLocation, item.storage_location_id)

        if location is None:
            raise HTTPException(
                status_code=422,
                detail=f"Место хранения с ID {item.storage_location_id} не найдено"
            )

    data = item.model_dump()

    for field, value in data.items():
        setattr(existing_item, field, value)

    db.commit()
    db.refresh(existing_item)

    return existing_item


@router.patch(
    "/{item_id}",
    response_model=InventoryRead,
    summary="Partially update inventory item",
    description="Update only the provided fields of an inventory item.",
    responses={
        404: {
            "model": InventoryErrorResponse,
            "description": "Inventory item not found"
        },
        422: {
            "model": InventoryErrorResponse,
            "description": "Invalid input data"
        }
    }
)
def patch_inventory_item(
    item_id: int,
    item: InventoryPatch,
    db: Session = Depends(get_db)
):
    existing_item = db.get(StockItem, item_id)

    require_inventory_item(existing_item, item_id)

    data = item.model_dump(exclude_unset=True)

    # PATCH проверяет обе даты после объединения с текущей записью.
    current = {field: getattr(existing_item, field) for field in InventoryCreate.model_fields}
    try:
        InventoryCreate.model_validate(current | data)
    except ValidationError as exc:
        errors = [dict(error, loc=("body", *error["loc"])) for error in exc.errors()]
        raise RequestValidationError(errors) from exc

    if data.get("category_id") is not None:
        category = db.get(Category, data["category_id"])

        if category is None:
            raise HTTPException(
                status_code=422,
                detail=f"Категория с ID {data['category_id']} не найдена"
            )

    if data.get("storage_location_id") is not None:
        location = db.get(StorageLocation, data["storage_location_id"])

        if location is None:
            raise HTTPException(
                status_code=422,
                detail=f"Место хранения с ID {data['storage_location_id']} не найдено"
            )

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
        },
        422: {
            "model": InventoryErrorResponse,
            "description": "Invalid inventory item ID"
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
            detail=f"Позиция с ID {item_id} не найдена"
        )
    return item
