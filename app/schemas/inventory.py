from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models import ExpiryStatus

class InventoryBase(BaseModel):
    name: str
    quantity: float

class InventoryUpdateResponse(BaseModel):
    id: int
    item: InventoryBase

class InventoryDeleteResponse(BaseModel):
    id: int

class InventoryErrorResponse(BaseModel):
    detail: str

class InventoryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    quantity: float
    unit: str

    category_id: int | None
    storage_location_id: int | None

    purchase_date: date | None
    expiry_date: date | None
    comment: str | None

    status: ExpiryStatus
    status_label: str
    days_left: int | None

    created_at: datetime
    updated_at: datetime

class InventoryCreate(BaseModel):
    name: str = Field(min_length=1)
    quantity: float = Field(gt=0)
    unit: str = "шт"

    category_id: int | None = None
    storage_location_id: int | None = None

    purchase_date: date | None = None
    expiry_date: date | None = None
    comment: str | None = None
    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        value = value.strip()

        if not value:
            raise ValueError("Название продукта не может быть пустым")

        return value