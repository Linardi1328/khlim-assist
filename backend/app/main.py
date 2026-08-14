from fastapi import FastAPI

from app.api.routes import conversations, events, handoffs, health
from app.api.webhooks import whatsapp
from app.config.settings import Settings, get_settings


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved_settings = settings or get_settings()
    app = FastAPI(
        title=resolved_settings.app_name,
        version="0.1.0",
        description="KHLIM Assist v0.1 Phase 0 backend foundation.",
    )

    app.include_router(health.router)
    app.include_router(events.router, prefix=resolved_settings.api_v1_prefix)
    app.include_router(conversations.router, prefix=resolved_settings.api_v1_prefix)
    app.include_router(handoffs.router, prefix=resolved_settings.api_v1_prefix)
    app.include_router(whatsapp.router, prefix=resolved_settings.api_v1_prefix)
    app.dependency_overrides[get_settings] = lambda: resolved_settings

    return app


app = create_app()
