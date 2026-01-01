from __future__ import annotations

import json

from fastapi import BackgroundTasks, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.admin import router as admin_router
from app.api.auth import router as auth_router
from app.api.service import InvalidApiTokenError, router as service_router
from app.core.config import settings
from app.core.database import init_db
from app.core.logging import setup_logging
from app.services.processor import handle_webhook
from app.utils.security import verify_signature

app = FastAPI(title="Instagram DM Bot")

@app.exception_handler(InvalidApiTokenError)
async def invalid_api_token_handler(
    request: Request, exc: InvalidApiTokenError
) -> JSONResponse:
    token = exc.api_token
    return JSONResponse(
        status_code=401,
        content={"error": f"Invalid API token: '{token}'", "api_token": token},
    )

origins = [origin.strip() for origin in settings.ADMIN_UI_ORIGINS.split(",") if origin]
if origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

@app.on_event("startup")
async def on_startup() -> None:
    setup_logging()
    await init_db()


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@app.post("/webhook")
async def webhook(request: Request, background_tasks: BackgroundTasks) -> dict:
    body = await request.body()

    if settings.WEBHOOK_SECRET:
        signature = request.headers.get("x-webhook-signature")
        if not verify_signature(settings.WEBHOOK_SECRET, body, signature):
            raise HTTPException(status_code=401, detail="Invalid signature")

    try:
        payload = json.loads(body.decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="Invalid JSON") from exc

    background_tasks.add_task(handle_webhook, payload)
    return {"status": "accepted"}


app.include_router(auth_router)
app.include_router(admin_router)
app.include_router(service_router)
