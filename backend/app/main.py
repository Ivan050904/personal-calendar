from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.core.auth_middleware import AuthMiddleware
from app.core.config import get_settings
from app.core.errors import register_exception_handlers
from app.core.rate_limit import SimpleRateLimitMiddleware


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name)
    register_exception_handlers(app)
    app.add_middleware(SimpleRateLimitMiddleware)
    app.add_middleware(AuthMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(api_router, prefix=settings.api_prefix)
    # Convenience alias without versioning for local smoke checks
    app.include_router(api_router)
    return app


app = create_app()
