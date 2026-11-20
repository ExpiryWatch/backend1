from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

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

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request,
    exc: RequestValidationError
):
    messages = []

    for error in exc.errors():
        field = ".".join(str(part) for part in error["loc"])
        message = f"{field}: {error['msg']}"
        messages.append(message)

    return JSONResponse(
        status_code=422,
        content={"detail": "; ".join(messages)}
    )