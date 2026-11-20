from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.queries import list_categories_with_counts


router = APIRouter(prefix="/categories", tags=["categories"])


class CategoryResponse(BaseModel):
    id: int
    name: str
    items_count: int


@router.get(
    "/",
    response_model=list[CategoryResponse],
    summary="Get all categories",
    description="Return categories and the number of items in each category."
)
def get_categories(db: Session = Depends(get_db)):
    categories = list_categories_with_counts(db)

    result = []

    for category, count in categories:
        result.append({
            "id": category.id,
            "name": category.name,
            "items_count": count
        })

    return result