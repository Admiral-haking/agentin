# Instagram DM Bot (FastAPI + PostgreSQL)

A webhook-driven DM assistant that stores conversation history, routes between OpenAI and DeepSeek, and sends replies via your outbound API.

## Quick start

1) Create and activate a virtualenv:

```
python3 -m venv .venv
source .venv/bin/activate
```

Windows:

```
.venv\Scripts\activate
```

2) Install dependencies:

```
pip install -r requirements.txt
```

3) (Recommended) Start Postgres via Docker:

```
docker compose up -d db
```

Update `DATABASE_URL` in `.env` to match the Docker database:

```
DATABASE_URL=postgresql+asyncpg://dm_bot:dm_bot@localhost:5433/dm_bot
```

4) Create your environment file:

```
cp .env.example .env
```

Set Directam webservice settings in `.env`:

```
DIRECTAM_BASE_URL=https://directam-plus.manymessage.com/webservice
SERVICE_API_KEY=YOUR_API_KEY
```

5) Run sanity checks:

```
python -m compileall app
python -m uvicorn app.main:app --reload
```

Notes:
- If `python` or `uvicorn` is not found, ensure Python is installed and your virtualenv is activated.

## Admin panel

Backend admin APIs are under `/auth/*` and `/admin/*`. The React Admin UI lives in `admin-ui/`.

Admin auth env (minimum):

```
JWT_SECRET_KEY=YOUR_JWT_SECRET
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7
ADMIN_UI_ORIGINS=http://localhost:5173
```

Auth uses short-lived access tokens and refresh rotation via `/auth/refresh`.

Run locally:

```
cd admin-ui
npm install
cp .env.example .env
npm run dev
```

Ensure the backend allows CORS for your admin UI origin using `ADMIN_UI_ORIGINS`.

Admin UI highlights:
- User Behavior: extracted patterns + confidence per user.
- AI Context: view injected context + simulate replies (no send).
- Support Tickets + Followups: manage complaints and reminder tasks.
- Analytics dashboard: intents, patterns, latency, and top keywords.

Bootstrap the first admin user:

```
python -m app.admin.bootstrap --email admin@example.com --password 'YOUR_STRONG_PASSWORD'
```

If `--password` is omitted, the script will prompt securely.

## Product sync

Enable the catalog feature and set sync sources in `.env`:

```
PRODUCTS_FEATURE_ENABLED=true
TOROB_PRODUCTS_URL=https://ghlbedovom.com/api/torob/products
SITEMAP_URL=https://ghlbedovom.com/sitemap.xml
PRODUCT_SCRAPE_ENABLED=true
ORDER_FORM_ENABLED=true
```

Run a sync manually (admin only):

```
POST /admin/products/sync
```

Or run it from the server:

```
python -m app.admin.sync_products
```

Schedule with cron (example every 6 hours):

```
0 */6 * * * cd /opt/agentin && /opt/agentin/.venv/bin/python -m app.admin.sync_products >> /var/log/agentin_product_sync.log 2>&1
```

Bot behavior:
- If a user asks for products or prices and there are matches, the bot sends a product carousel/button before calling the LLM.
- Matched products are also injected into the AI context so the model can answer with accurate prices and links.
- Order capture can be enabled with `ORDER_FORM_ENABLED=true`.

## Follow-ups

Enable a single safe follow-up after purchase intent:

```
FOLLOWUP_ENABLED=true
FOLLOWUP_DELAY_HOURS=12
FOLLOWUP_MESSAGE=اگر سوال یا خریدی داشتید، من در خدمتم.
```

Follow-up tasks are stored in `followup_tasks` and can be managed from the admin UI.

## Analytics + AI Context

The backend exposes aggregated analytics:

- `GET /admin/analytics/summary?days=30`

The AI context viewer:

- `GET /admin/ai/context?conversation_id=...`
- `POST /admin/ai/simulate_reply`

## Docker (minimal)

```
docker compose up --build
```

Update `docker-compose.yml` and `.env` values with your Directam base URL and secrets.

## Webhook endpoint

- `POST /webhook`
- Optional signature: `x-webhook-signature` (hex HMAC-SHA256 of the raw body) when `WEBHOOK_SECRET` is set.

Example payload (adjust field names to your provider):

```json
{
  "sender_id": "123456",
  "receiver_id": "987654",
  "message_type": "text",
  "text": "Hello, I need help",
  "is_admin": false,
  "timestamp": 1735651200
}
```

## Outbound API mapping

The sender assumes these endpoints and payloads:

- `POST /send/text` with `{ "receiver_id": "...", "text": "..." }`
- `POST /send/photo` with `{ "receiver_id": "...", "image_url": "..." }`
- `POST /send/video` with `{ "receiver_id": "...", "video_url": "..." }`
- `POST /send/audio` with `{ "receiver_id": "...", "audio_url": "..." }`
- `POST /send/button-text` with `{ "receiver_id": "...", "text": "...", "buttons": [{"type":"web_url","title":"...","url":"..."}] }`
- `POST /send/quick-reply` with `{ "receiver_id": "...", "text": "...", "quick_replies": [{"title":"...","payload":"..."}] }`
- `POST /send/generic-template` with `{ "receiver_id": "...", "elements": [...] }`

Adjust field names in `app/services/sender.py` if your provider differs. Buttons support `type` (`web_url` or `postback`) with `url` or `payload`.

## Troubleshooting

- `405 Not Allowed` usually means the base URL is wrong or the HTTP method is incorrect.
- `Request from invalid endpoint` means your server IP/origin or endpoint is not whitelisted in the DMPlus/Directam panel.

## Notes

- System prompts are stored in `app/prompts/` and loaded on demand.
- Replace the prompt text in `app/prompts/system.txt` with your preferred Persian copy.
- The 24-hour rule is enforced using `conversations.last_user_message_at`.
- Admin messages are stored but ignored to prevent reply loops.
- Admin endpoints require JWT; unauthenticated requests are rejected.
- Consider periodic cleanup of `app_logs` and `audit_logs` (e.g., delete entries older than 30-90 days).
