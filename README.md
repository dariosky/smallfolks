# Smallfolk

A calm, inspectable city-life simulation. This first POC is a deliberately small,
fixed-seed town: ten residents, homes, workplace and shop places, Pippin the dog,
two parked vehicles, scripted placeholder activities, and an inspectable decision
trace. The partial `poc-9` train work is intentionally unfinished: backend service
state and the frontend animation do not yet share one contract.

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

## POC API and save compatibility

- `GET /api/worlds` lists saved world metadata, including `world_format_version`; `POST /api/worlds` creates (or reloads) the deterministic fixed-seed fixture.
- `POST /api/worlds/{id}/advance` advances its authoritative clock and saves it.
- `GET /api/worlds/{id}/render-state`, `/entities/{id}`, and `/events` power the map and inspector.

SQLite is used for this POC's durable snapshot so it starts without external
services. SQLModel owns the persistence model and Alembic owns its schema
migration. The environment structure remains ready for a PostgreSQL URL before
the broader relational entity/event schema arrives.

Snapshots carry three independent compatibility markers: `world_format_version`
describes the JSON shape, `generation_version` identifies the town generator, and
`simulation_version` identifies behaviour rules. Format-0 snapshots (the original
POC shape with no format/revision fields) are loaded additively as format 1 and are
only rewritten after a state-changing command. A future/removed format is rejected
with HTTP 409 and an explanation; it is never silently reset or overwritten.

The current format also has a command `revision`; each successful advance increments
it. It is groundwork for stale-write rejection in step 1, not concurrency control yet.

## Checks

```bash
.venv/bin/pytest backend/tests
cd frontend && npm run lint && npm run build
```

The backend test suite creates a temporary SQLite database, applies Alembic
migrations to it, and deletes it afterward. It does not read or write the database
configured in `backend/.env`.

## Next phases

1. Add generated blocks, parcels, and validated pedestrian/road graphs from a town brief.
2. Replace the fixed schedule with needs, commitments, routes, and explainable choices.
3. Add full relational persistence, migrations, events/checkpoints, and save slots.
4. Introduce economy, vehicles/rail, pets, relationships, and simulation LOD.
