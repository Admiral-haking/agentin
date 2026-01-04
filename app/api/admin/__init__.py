from fastapi import APIRouter

from app.api.admin.campaigns import router as campaigns_router
from app.api.admin.conversations import router as conversations_router
from app.api.admin.faqs import router as faqs_router
from app.api.admin.logs import router as logs_router
from app.api.admin.messages import router as messages_router
from app.api.admin.products import router as products_router
from app.api.admin.assistant import router as assistant_router
from app.api.admin.ai_context import router as ai_context_router
from app.api.admin.behavior import router as behavior_router
from app.api.admin.settings import router as settings_router
from app.api.admin.users import router as users_router
from app.api.admin.directam import router as directam_router
from app.api.admin.health import router as health_router

router = APIRouter()
router.include_router(campaigns_router)
router.include_router(faqs_router)
router.include_router(products_router)
router.include_router(conversations_router)
router.include_router(messages_router)
router.include_router(settings_router)
router.include_router(logs_router)
router.include_router(assistant_router)
router.include_router(ai_context_router)
router.include_router(behavior_router)
router.include_router(users_router)
router.include_router(directam_router)
router.include_router(health_router)
