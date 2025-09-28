from fastapi import FastAPI
from app.core.config import settings
from app.api.routes.schemas import router as schemas_router

app = FastAPI(title=settings.APP_NAME)
app.include_router(schemas_router)

@app.get("/health")
def health():
    return {"ok": True}
