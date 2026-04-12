# TremorGuard Backend

FastAPI + SQLAlchemy 2 backend for TremorGuard stage-one data platform.

## What is included

- Dual-database setup for `identity` and `clinical` data
- Alembic migrations for both databases
- Seed data that mirrors the current frontend demo
- REST API with OpenAPI output
- Device ingest endpoint with device-key auth and idempotency support
- Authenticated AI chat endpoint at `POST /v1/ai/chat`

## Local development

1. Create and activate a virtual environment.
2. Install the package:

```bash
pip install -e ".[dev]"
```

3. Copy `.env.example` to `.env` if you want to override defaults.
   For AI chat, set `DASHSCOPE_API_KEY` in `.env`.

```env
DASHSCOPE_API_KEY=your-api-key
DASHSCOPE_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
```

   If you need another region, replace `DASHSCOPE_BASE_URL` with:
   - Singapore: `https://dashscope-intl.aliyuncs.com/compatible-mode/v1`
   - US (Virginia): `https://dashscope-us.aliyuncs.com/compatible-mode/v1`
4. Run migrations and seed data:

```bash
python -m app.scripts.run_migrations
python -m app.scripts.seed
```

5. Start the API:

```bash
uvicorn app.main:app --reload
```

6. Export the OpenAPI contract when needed:

```bash
python -m app.scripts.export_openapi
```

## Demo credentials

- User email: `patient@tremorguard.local`
- User password: `tg-demo-password`
- Device key: `tg-device-demo-key`

## Docker

Use the repository root `docker-compose.yml` to start the full local stack:

```bash
docker compose up --build
```
