from fastapi import FastAPI

from app.routers.inventory import router as inventory_router
from app.routers.categories import router as categories_router
from app.routers.storage_locations import router as storage_locations_router

app = FastAPI()

app.include_router(inventory_router)
app.include_router(categories_router)
app.include_router(storage_locations_router)

@app.get("/")
def root():
    return {"message": "Backend is running"}