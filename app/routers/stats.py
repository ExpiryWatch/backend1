
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.queries import get_stats


router = APIRouter(prefix="/stats", tags=["stats"])


class StatsResponse(BaseModel):
    total: int
    fresh: int
    expiring_soon: int
    expired: int
    no_date: int


@router.get(
    "/",
    response_model=StatsResponse,
    summary="Get inventory statistics",
    description="Return the total number of inventory items and their counts by expiry status."
)
def get_inventory_stats(db: Session = Depends(get_db)):
    return get_stats(db)