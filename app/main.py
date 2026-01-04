from __future__ import annotations

import asyncio
import json
from urllib.parse import urlparse

from fastapi import BackgroundTasks, FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
import httpx

from app.api.admin import router as admin_router
from app.api.auth import router as auth_router
from app.api.service import InvalidApiTokenError, router as service_router
from app.core.config import settings
from app.core.database import init_db
from app.core.logging import setup_logging
from app.services.followups import followup_worker
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
    app.state.followup_stop = asyncio.Event()
    app.state.followup_task = asyncio.create_task(
        followup_worker(app.state.followup_stop)
    )


@app.on_event("shutdown")
async def on_shutdown() -> None:
    stop_event = getattr(app.state, "followup_stop", None)
    task = getattr(app.state, "followup_task", None)
    if stop_event:
        stop_event.set()
    if task:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass


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


@app.api_route("/media-proxy", methods=["GET", "HEAD"])
async def media_proxy(request: Request, url: str = Query(..., min_length=8)) -> Response:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise HTTPException(status_code=400, detail="Invalid URL scheme")
    allowed_hosts = {
        host.strip().lower()
        for host in settings.MEDIA_PROXY_ALLOWED_HOSTS.split(",")
        if host.strip()
    }
    hostname = parsed.hostname.lower() if parsed.hostname else ""
    host_allowed = any(
        hostname == allowed or hostname.endswith(f".{allowed}")
        for allowed in allowed_hosts
    )
    if hostname and not host_allowed:
        raise HTTPException(status_code=400, detail="Host not allowed")

    timeout = httpx.Timeout(settings.MEDIA_PROXY_TIMEOUT_SEC)
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
        try:
            method = "HEAD" if request.method == "HEAD" else "GET"
            upstream = await client.request(method, url)
            if upstream.status_code in {405, 501} and method == "HEAD":
                upstream = await client.get(url)
        except httpx.HTTPError as exc:
            raise HTTPException(status_code=502, detail=f"Upstream error: {exc}") from exc

    if upstream.status_code >= 400:
        raise HTTPException(status_code=502, detail="Upstream returned error")

    content_type = upstream.headers.get("content-type", "")
    if not content_type.startswith("image/"):
        raise HTTPException(status_code=415, detail="Unsupported media type")
    content_length = upstream.headers.get("content-length")
    if content_length and content_length.isdigit():
        if int(content_length) > settings.MEDIA_PROXY_MAX_BYTES:
            raise HTTPException(status_code=413, detail="Image too large")

    content = b"" if request.method == "HEAD" else upstream.content
    if content and len(content) > settings.MEDIA_PROXY_MAX_BYTES:
        raise HTTPException(status_code=413, detail="Image too large")

    headers = {
        "Cache-Control": "public, max-age=3600",
    }
    return Response(content=content, media_type=content_type, headers=headers)


app.include_router(auth_router)
app.include_router(admin_router)
app.include_router(service_router)
