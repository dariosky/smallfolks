from contextlib import asynccontextmanager

from fastapi import FastAPI
from slowapi.errors import RateLimitExceeded

import persistence.models  # noqa: F401 - registers snapshot tables with SQLModel
import settings
from middlewares import add_middlewares, get_middlewares
from rate_limits import limiter, rate_limit_exceeded_handler
from routes.health import router as health_router
from routes.html import router as html_router
from routes.worlds import router as worlds_router
from services.static_files import ImmutableStaticFiles


@asynccontextmanager
async def app_lifespan(_: FastAPI):
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title="Smallfolk",
        description="A calm, inspectable city-life simulation.",
        version="0.1.0",
        docs_url="/docs" if settings.DEBUG else None,
        redoc_url="/redoc" if settings.DEBUG else None,
        openapi_url="/openapi.json" if settings.DEBUG else None,
        middleware=get_middlewares(),
        swagger_ui_parameters={"defaultModelsExpandDepth": 0},
        lifespan=app_lifespan,
    )
    add_middlewares(app)
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)

    assets_path = settings.DIST_DIR / "assets"
    if assets_path.exists():
        app.mount(
            "/assets",
            ImmutableStaticFiles(directory=str(assets_path)),
            name="assets",
        )

    app.include_router(health_router, prefix=settings.API_PREFIX, tags=["health"])
    app.include_router(worlds_router, prefix=settings.API_PREFIX, tags=["worlds"])

    if settings.ENABLE_HTML_SERVING:
        app.include_router(html_router)

    return app
