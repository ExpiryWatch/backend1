from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.exc import IntegrityError

from app.routers.inventory import router as inventory_router
from app.routers.categories import router as categories_router
from app.routers.storage_locations import router as storage_locations_router
from app.routers.stats import router as stats_router

app = FastAPI()

app.include_router(inventory_router)
app.include_router(categories_router)
app.include_router(storage_locations_router)
app.include_router(stats_router)
app.mount("/ui", StaticFiles(directory=Path(__file__).resolve().parent.parent / "frontend", html=True), name="ui")

@app.get("/")
def root():
    return {"message": "Backend is running"}

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request,
    exc: RequestValidationError
):
    messages = []
    errors = []
    translations = {
        "missing": "Обязательное поле не заполнено",
        "string_too_short": "Поле не должно быть пустым",
        "string_too_long": "Превышена допустимая длина поля",
        "string_type": "Укажите текст",
        "float_type": "Количество должно быть числом",
        "greater_than": "Значение должно быть больше нуля",
        "greater_than_equal": "Значение меньше допустимого",
        "less_than_equal": "Значение превышает допустимый максимум",
        "finite_number": "Количество должно быть конечным числом",
        "int_type": "Идентификатор должен быть целым числом",
        "int_parsing": "Идентификатор должен быть целым числом",
        "literal_error": "Выберите допустимое значение",
        "enum": "Выберите допустимый статус",
        "extra_forbidden": "Неизвестное поле; статус и дни рассчитывает сервер",
        "date_from_datetime_parsing": "Укажите существующую дату в формате ГГГГ-ММ-ДД",
        "date_parsing": "Укажите существующую дату в формате ГГГГ-ММ-ДД",
        "json_invalid": "Некорректный JSON",
        "model_attributes_type": "Тело запроса должно быть объектом JSON",
    }

    for error in exc.errors():
        field = ".".join(str(part) for part in error["loc"])
        reason = translations.get(error["type"], "Некорректное значение")
        if error["type"] == "value_error":
            reason = error["msg"].removeprefix("Value error, ")
        message = f"{field}: {reason}"
        messages.append(message)
        errors.append({"loc": list(error["loc"]), "msg": reason})

    return JSONResponse(
        status_code=422,
        content={"detail": "; ".join(messages), "errors": errors}
    )


@app.exception_handler(IntegrityError)
async def integrity_exception_handler(request: Request, exc: IntegrityError):
    return JSONResponse(status_code=409, content={"detail": "Операция нарушает ограничения базы данных. Проверьте связанные данные."})
