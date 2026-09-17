from fastapi import FastAPI
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from app.api import router
from app.config import get_settings

settings = get_settings()

app = FastAPI(title=settings.app_name, version="1.0.0")
app.include_router(router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.exception_handler(ValidationError)
async def pydantic_validation_handler(_, exc: ValidationError) -> JSONResponse:
    return JSONResponse(status_code=422, content={"detail": exc.errors()})
