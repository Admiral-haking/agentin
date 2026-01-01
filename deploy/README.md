# Production Deploy (systemd + nginx)

This guide assumes:
- API domain: api.teamcore.ir
- Admin UI domain: admin.teamcore.ir
- PostgreSQL runs on the same server (default 5432)
- App path: /opt/agentin

## 1) Server prerequisites

```bash
sudo apt update
sudo apt install -y python3-venv python3-pip python3-dev build-essential \
  nginx postgresql postgresql-contrib nodejs npm
```

If you want a newer Node.js for faster builds, install Node 20+ and re-run the
admin build steps.

## 2) Create a system user and app directory

```bash
sudo useradd -m -s /bin/bash agentin
sudo mkdir -p /opt/agentin
sudo chown -R agentin:agentin /opt/agentin
```

## 3) Copy the project to the server

Either clone from git (recommended) or upload the repo contents to `/opt/agentin`.

```bash
sudo -u agentin bash -lc 'cd /opt/agentin && git clone <YOUR_REPO_URL> .'
```

## 4) Create the database

```bash
sudo -u postgres psql <<'SQL'
CREATE USER dm_bot WITH PASSWORD 'YOUR_DB_PASSWORD';
CREATE DATABASE dm_bot OWNER dm_bot;
SQL
```

## 5) Create the API environment file

```bash
sudo -u agentin cp /opt/agentin/deploy/.env.server.example /opt/agentin/.env
sudo -u agentin nano /opt/agentin/.env
```

Update at least:
- `DATABASE_URL` (use your real DB password)
- `DIRECTAM_BASE_URL`, `SERVICE_API_KEY`
- `OPENAI_API_KEY` or `DEEPSEEK_API_KEY`
- `JWT_SECRET_KEY`
- `ADMIN_UI_ORIGINS=https://admin.teamcore.ir`

## 6) Install API dependencies and migrate

```bash
sudo -u agentin bash -lc 'cd /opt/agentin && python3 -m venv .venv'
sudo -u agentin bash -lc 'cd /opt/agentin && source .venv/bin/activate && pip install -r requirements.txt'
sudo -u agentin bash -lc 'cd /opt/agentin && source .venv/bin/activate && alembic upgrade head'
```

Bootstrap the first admin user (use a placeholder password):
```bash
sudo -u agentin bash -lc "cd /opt/agentin && source .venv/bin/activate && \
python -m app.admin.bootstrap --email admin@example.com --password 'YOUR_STRONG_PASSWORD'"
```

## 7) Build the admin UI

```bash
sudo -u agentin bash -lc 'cd /opt/agentin/admin-ui && cp .env.example .env.production'
sudo -u agentin bash -lc "cd /opt/agentin/admin-ui && \
sed -i 's#http://localhost:8000#https://api.teamcore.ir#g' .env.production"
sudo -u agentin bash -lc 'cd /opt/agentin/admin-ui && npm install && npm run build'
```

## 8) systemd service

```bash
sudo cp /opt/agentin/deploy/systemd/agentin-api.service /etc/systemd/system/agentin-api.service
sudo systemctl daemon-reload
sudo systemctl enable --now agentin-api
sudo systemctl status agentin-api --no-pager
```

## 9) nginx config

```bash
sudo cp /opt/agentin/deploy/nginx/api.teamcore.ir.conf /etc/nginx/sites-available/api.teamcore.ir
sudo cp /opt/agentin/deploy/nginx/admin.teamcore.ir.conf /etc/nginx/sites-available/admin.teamcore.ir
sudo ln -s /etc/nginx/sites-available/api.teamcore.ir /etc/nginx/sites-enabled/api.teamcore.ir
sudo ln -s /etc/nginx/sites-available/admin.teamcore.ir /etc/nginx/sites-enabled/admin.teamcore.ir
sudo nginx -t
sudo systemctl reload nginx
```

## 10) HTTPS (recommended)

```bash
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d api.teamcore.ir -d admin.teamcore.ir
```

## 11) Smoke checks

```bash
curl -s https://api.teamcore.ir/health
```

Login to the admin UI at `https://admin.teamcore.ir`.

## 12) Optional: scheduled contacts import

If you receive a contacts JSON/CSV file (because Directam has no full contacts API),
you can schedule an hourly import using cron:

```bash
sudo cp /opt/agentin/deploy/cron/agentin-contacts-import.cron /etc/cron.d/agentin-contacts-import
sudo mkdir -p /opt/agentin/import
sudo touch /opt/agentin/import/contacts.json
```

Update the cron file path/format if you use CSV.

## Notes

- If you change `/opt/agentin/.env`, restart the API:
  `sudo systemctl restart agentin-api`
- Ensure DNS for both domains points to this server before issuing certificates.
