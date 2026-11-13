from pydantic import BaseModel

class InventoryBase(BaseModel):
    name: str
    quantity: float

class InventoryUpdateResponse(BaseModel):
    id: int
    item: InventoryBase

class InventoryDeleteResponse(BaseModel):
    id: int