# LoLAnalytics

REST-first web app for collecting League of Legends Ranked Flex activity, monitoring Riot IDs, and visualizing active time windows.

## Architecture

- `frontend`: Vue 3 + Vite UI.
- `api`: FastAPI REST API under `/api/v1`.
- `worker`: background collection and monitor worker.
- `mysql`: MySQL 8 storage.

SQLite and business CLI commands are no longer used.

## Run With Docker Compose

```powershell
$env:ADMIN_PASSWORD="change-me"
$env:JWT_SECRET="change-this-secret"
docker compose up --build
```

Open:

```text
http://127.0.0.1:8080
```

Login with username `admin` and the `ADMIN_PASSWORD` value.

Save your Riot API key in Settings. The app does not read Riot API keys from `.env`.

## REST API

All application endpoints are under `/api/v1`.

- `POST /api/v1/auth/token`
- `GET /api/v1/auth/session`
- `POST /api/v1/collection-jobs`
- `GET /api/v1/collection-jobs`
- `GET /api/v1/collection-jobs/{id}`
- `GET /api/v1/stats`
- `GET /api/v1/monitors`
- `POST /api/v1/monitors`
- `PATCH /api/v1/monitors/{id}`
- `DELETE /api/v1/monitors/{id}`
- `POST /api/v1/monitor-checks`
- `GET /api/v1/settings`
- `PUT /api/v1/settings`
- `POST /api/v1/settings/riot-api-key-checks`
- `GET /api/v1/logs`
- `DELETE /api/v1/logs`

Authentication uses OAuth2 password flow plus JWT bearer tokens. The frontend stores the token in session storage and sends `Authorization: Bearer <token>`.

## Local API Development

Install backend dependencies, then run migrations and the API:

```powershell
pip install -e .
$env:DATABASE_URL="mysql+pymysql://lolanalytics:lolanalytics@127.0.0.1:3306/lolanalytics"
$env:ADMIN_PASSWORD="admin"
$env:JWT_SECRET="dev-secret"
alembic upgrade head
uvicorn loltimecheck.web.app:app --host 127.0.0.1 --port 8000
```

Run the worker separately:

```powershell
python -m loltimecheck.worker
```

Run the frontend:

```powershell
cd frontend
npm install
npm run dev
```

## Data Sources

- League queue: `RANKED_FLEX_SR`
- Match queue id: `440`
- Supported servers are configured in `loltimecheck/core/constants.py`.
