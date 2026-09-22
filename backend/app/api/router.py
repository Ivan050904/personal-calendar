from fastapi import APIRouter

from app.api.routes import ai, auth, entities, health, smart_day, whisper

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(entities.router)
api_router.include_router(smart_day.router)
api_router.include_router(ai.router)
api_router.include_router(whisper.router)
