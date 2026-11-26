import re
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models import ExpiryStatus

Name = Annotated[str, Field(min_length=1, max_length=255)]
Unit = Annotated[str, Field(min_length=1, max_length=16)]
Quantity = Annotated[float, Field(gt=0, le=99999999.99, allow_inf_nan=False, strict=True)]
ReferenceId = Annotated[int, Field(gt=0, strict=True)]


class InventoryBase(BaseModel):
    name: str
    quantity: float


class InventoryUpdateResponse(BaseModel):
    id: int
    item: InventoryBase


class InventoryDeleteResponse(BaseModel):
    id: int


class InventoryValidationIssue(BaseModel):
    loc: list[str | int]
    msg: str


class InventoryErrorResponse(BaseModel):
    detail: str
    errors: list[InventoryValidationIssue] | None = None


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
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: Name
    quantity: Quantity
    unit: Unit = "шт"
    category_id: ReferenceId | None = None
    storage_location_id: ReferenceId | None = None
    purchase_date: date | None = None
    expiry_date: date | None = None
    comment: str | None = None

    @field_validator("quantity")
    @classmethod
    def quantity_precision(cls, value):
        # NUMERIC(10, 2) иначе округлит сохранённое количество при чтении.
        if Decimal(str(value)).normalize().as_tuple().exponent < -2:
            raise ValueError("Количество должно иметь не больше двух знаков после запятой")
        return value

    @field_validator("purchase_date", "expiry_date", mode="before")
    @classmethod
    def calendar_date(cls, value):
        if value is None or type(value) is date:
            return value
        if isinstance(value, str) and re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value):
            return value
        raise ValueError("Укажите дату в формате ГГГГ-ММ-ДД")


class InventoryPatch(InventoryCreate):
    name: Name | None = None
    quantity: Quantity | None = None
    unit: Unit | None = None

    @field_validator("name", "quantity", "unit", mode="before")
    @classmethod
    def required_if_present(cls, value):
        if value is None:
            raise ValueError("Обязательное поле нельзя очистить")
        return value


class InventoryPut(InventoryCreate):
    unit: Unit
    category_id: ReferenceId | None
    storage_location_id: ReferenceId | None
    purchase_date: date | None
    expiry_date: date | None
    comment: str | None
