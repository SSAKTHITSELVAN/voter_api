from contextlib import asynccontextmanager
from pathlib import Path

import fastapi
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from fastapi.staticfiles import StaticFiles

from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger
from app.db.init_db import init_db
from app.routers import (
    auth_router,
    users_router,
    buildings_router,
    households_router,
    verification_router,
)

configure_logging()
logger = get_logger(__name__)
settings = get_settings()
upload_dir = Path(settings.UPLOAD_DIR).resolve()
upload_dir.mkdir(parents=True, exist_ok=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting up – initialising database …")
    await init_db()
    logger.info("Startup complete.")
    yield
    logger.info("Shutting down.")


app = FastAPI(
    title="Voter Data Collection API",
    version="1.0.0",
    description="Field data collection and verification API for voter surveys.",
    lifespan=lifespan,
    # Hide the default Swagger auth UI — we replace it below
    swagger_ui_oauth2_redirect_url=None,
)

# ── CORS ──────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(auth_router)
app.include_router(users_router)
app.include_router(buildings_router)
app.include_router(households_router)
app.include_router(verification_router)
app.mount(
    settings.UPLOAD_URL_PREFIX,
    StaticFiles(directory=upload_dir),
    name="uploads",
)


# ── Health ────────────────────────────────────────────────────────────────────
@app.get("/health", tags=["Health"])
async def health():
    return {"status": "ok"}


# ── Custom OpenAPI: replace OAuth2 form with a plain Bearer token input ───────
def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema

    schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )

    # Replace every security scheme with a single HTTPBearer entry
    schema["components"]["securitySchemes"] = {
        "BearerAuth": {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
            "description": "Paste the JWT token returned by **POST /auth/login**",
        }
    }

    # Point every operation to use BearerAuth
    for path in schema.get("paths", {}).values():
        for operation in path.values():
            if "security" in operation:
                operation["security"] = [{"BearerAuth": []}]

    app.openapi_schema = schema
    return app.openapi_schema


app.openapi = custom_openapi
