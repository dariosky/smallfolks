# Smallfolk

A calm, inspectable city-life simulation. This first POC is a deliberately small,
fixed-seed town: ten residents, homes, workplace and shop places, Pippin the dog,
two vehicles, deterministic activity transitions, and an inspectable decision trace.

## Stack

- FastAPI
- SQLModel
- Alembic
- PostgreSQL
- React
- Vite

## Local development

### Backend (port 5340)

```bash
uv sync --group dev
cd backend
../.venv/bin/python run_dev.py
```

Before the first backend run, apply the schema migrations:

```bash
cd backend
../.venv/bin/alembic upgrade head
```

### Frontend (port 5341)

```bash
cd frontend
npm install
npm run dev
```

## Environment

The backend reads configuration from `backend/.env`. The starter generates local
defaults for:

- `ENVIRONMENT`
- `SESSION_SECRET_KEY`
- `DATABASE_URL`
- `BASE_URL`
- `API_PREFIX`
- `CORS_ORIGINS`
- `SITE_NAME`
- `ENABLE_HTML_SERVING`

The Vite dev server proxies `/api` to the backend. In production, FastAPI serves
the compiled `frontend/dist` bundle when `ENABLE_HTML_SERVING=true`.

## POC API

- `GET /api/worlds` lists saved world metadata; `POST /api/worlds` creates (or reloads) the deterministic fixed-seed fixture.
- `POST /api/worlds/{id}/advance` advances its authoritative clock and saves it.
- `GET /api/worlds/{id}/render-state`, `/entities/{id}`, and `/events` power the map and inspector.

SQLite is used for this POC's durable snapshot so it starts without external
services. SQLModel owns the persistence model and Alembic owns its schema
migration. The environment structure remains ready for a PostgreSQL URL before
the broader relational entity/event schema arrives.

## Next phases

1. Add generated blocks, parcels, and validated pedestrian/road graphs from a town brief.
2. Replace the fixed schedule with needs, commitments, routes, and explainable choices.
3. Add full relational persistence, migrations, events/checkpoints, and save slots.
4. Introduce economy, vehicles/rail, pets, relationships, and simulation LOD.
