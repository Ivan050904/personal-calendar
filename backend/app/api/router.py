from fastapi import APIRouter

from app.api.routes import ai, auth, entities, health, smart_day, whisper
from app.api.routes import integration, calendar_occurrences, calendar_commands, accounts, calendars_v2, entities_v2, oauth, reads_v2, sync_v2

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(entities.router)
api_router.include_router(smart_day.router)
api_router.include_router(ai.router)
api_router.include_router(whisper.router)
api_router.include_router(integration.router)
api_router.include_router(calendar_occurrences.router)
api_router.include_router(calendar_commands.router)
api_router.include_router(accounts.router)
api_router.include_router(calendars_v2.router)
for v2_router in entities_v2.routers:
    api_router.include_router(v2_router)
api_router.include_router(reads_v2.router)
api_router.include_router(oauth.router)
api_router.include_router(sync_v2.router)
