from fastapi import APIRouter
from katrain.web.api.v1.endpoints import health, auth, analysis

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(analysis.router, prefix="/analysis", tags=["analysis"])
