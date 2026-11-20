from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.queries import list_storage_locations_with_counts


router = APIRouter(
    prefix="/storage-locations",
    tags=["storage-locations"]
)


class StorageLocationResponse(BaseModel):
    id: int
    name: str
    icon: str | None
    items_count: int


@router.get(
    "/",
    response_model=list[StorageLocationResponse],
    summary="Get all storage locations",
    description="Return storage locations and the number of items in each."
)
def get_storage_locations(db: Session = Depends(get_db)):
    locations = list_storage_locations_with_counts(db)

    result = []

    for location, count in locations:
        result.append({
            "id": location.id,
            "name": location.name,
            "icon": location.icon,
            "items_count": count
        })

    return result