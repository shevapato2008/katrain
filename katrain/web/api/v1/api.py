from fastapi import APIRouter
from katrain.web.api.v1.endpoints.payment_test import register_test_payment_routes
from katrain.web.core.config import settings
from katrain.web.api.v1.endpoints import (
    health,
    auth,
    analysis,
    games,
    users,
    live,
    tsumego,
    kifu,
    user_games,
    board,
    devices,
    vision,
    tutorials,
    platforms,
    reports,
    billing,
    paid_analysis,
    baipu,
    baipu_history,
    led,
    geometry,
    hint,
    ai_ladder,
    growth,
    kiosk_preferences,
)

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(analysis.router, prefix="/analysis", tags=["analysis"])
api_router.include_router(games.router, prefix="/games", tags=["games"])
api_router.include_router(user_games.router, prefix="/user-games", tags=["user-games"])
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(live.router, prefix="/live", tags=["live"])
api_router.include_router(tsumego.router, prefix="/tsumego", tags=["tsumego"])
api_router.include_router(kifu.router, prefix="/kifu", tags=["kifu"])
api_router.include_router(board.router, prefix="/board", tags=["board"])
api_router.include_router(devices.router, prefix="/devices", tags=["devices"])
api_router.include_router(vision.router, prefix="/vision", tags=["vision"])
api_router.include_router(tutorials.router, prefix="/tutorials", tags=["tutorials"])
api_router.include_router(platforms.router, prefix="/platforms", tags=["platforms"])
api_router.include_router(reports.router, prefix="/reports", tags=["reports"])
api_router.include_router(billing.router, prefix="/billing", tags=["billing"])
api_router.include_router(baipu.router, prefix="/baipu", tags=["baipu"])
api_router.include_router(baipu_history.router, prefix="/baipu/history", tags=["baipu-history"])
api_router.include_router(led.router, prefix="/led", tags=["led"])
api_router.include_router(geometry.router, prefix="/geometry", tags=["geometry"])
api_router.include_router(hint.router, prefix="/hint", tags=["hint"])
api_router.include_router(ai_ladder.router, prefix="/ai-ladder", tags=["ai-ladder"])
api_router.include_router(growth.router, prefix="/growth", tags=["growth"])
api_router.include_router(kiosk_preferences.router, prefix="/kiosk-preferences", tags=["kiosk-preferences"])

# Registration is configuration-gated; every mock write additionally verifies the actual TEST database.

register_test_payment_routes(api_router, runtime_settings=settings)


api_router.include_router(paid_analysis.router, prefix="/analysis", tags=["paid-analysis"])


# Authenticated by WeChat's signature, independent of new-order availability.
from katrain.web.api.v1.endpoints import payment_wechat

api_router.include_router(payment_wechat.router, prefix="/payments/wechat", tags=["wechat-payments"])
