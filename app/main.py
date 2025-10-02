# app/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.api.routes.schemas import router as schemas_router
from app.api.routes.auth import router as auth_router
from app.api.routes.accounts import router as accounts_router

app = FastAPI(title=settings.app_name)

# CORS (open for now; tighten to specific origins later)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],              # e.g., ["http://localhost:3000", "https://your-frontend.com"]
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(auth_router)
#app.include_router(accounts_router)
#app.include_router(schemas_router)

@app.get("/health")
def health():
    return {"ok": True}
