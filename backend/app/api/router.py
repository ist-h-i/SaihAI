from fastapi import APIRouter

from app.api.health import router as health_router
from app.api.bedrock import router as bedrock_router
from app.api.hitl import router as hitl_router
from app.api.integrations import router as integrations_router
from app.api.logs import router as logs_router
from app.api.members import router as members_router
from app.api.projects import router as projects_router
from app.api.simulate import router as simulate_router
from app.api.v1 import router as v1_router
from app.api.watchdog import router as watchdog_router

api_router = APIRouter(prefix="/api")
api_router.include_router(health_router)
api_router.include_router(projects_router)
api_router.include_router(members_router)
api_router.include_router(simulate_router)
api_router.include_router(v1_router)
api_router.include_router(logs_router)
api_router.include_router(hitl_router)
api_router.include_router(integrations_router)
api_router.include_router(bedrock_router)
api_router.include_router(watchdog_router)
