# app/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.api.routes.schemas import router as schemas_router
from app.api.routes.auth import router as auth_router
from app.api.routes.accounts import router as accounts_router
from app.api.routes.subscriptions import router as subscriptions_router
from app.api.routes.stripe_webhook import router as stripe_webhook_router
from app.api.routes.public_plans import router as public_plans_router
from app.api.routes.integrations import router as integrations_router
from app.api.routes.mapper import router as mapper_router
from app.api.routes.dashboard import router as dashboard_router
from app.api.routes.contact import router as contact_router
from app.api.routes.surveys import router as surveys_router
from app.api.routes.survey_public import router as survey_public_router

app = FastAPI(
    title=settings.app_name,
    docs_url="/gibberish-xyz-123",             # new Swagger UI path
    redoc_url=None,                            # disable ReDoc if you don't need it
    openapi_url="/gibberish-xyz-123/openapi.json"  # OpenAPI JSON path
)

# CORS (open for now; tighten to specific origins later)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://app.smartschema.io", "https://www.app.smartschema.io", "http://localhost:3000","http://localhost:3001","https://smartschema.io", "https://www.smartschema.io"],              # e.g., ["http://localhost:3000", "https://your-frontend.com"]
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(auth_router)
app.include_router(accounts_router)
app.include_router(schemas_router)
app.include_router(subscriptions_router)
app.include_router(stripe_webhook_router)
app.include_router(public_plans_router)
app.include_router(integrations_router)
app.include_router(mapper_router)
app.include_router(dashboard_router)
app.include_router(contact_router)
app.include_router(surveys_router)
app.include_router(survey_public_router)

@app.get("/health")
def health():
    return {"ok": True}
