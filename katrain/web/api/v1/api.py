from fastapi import APIRouter
from katrain.web.api.v1.endpoints import health, auth

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
