# AGENTS.md — Coding Agent Guidelines

## Project Overview

**semant_text_cl_app** collects human text-classification annotations for benchmarking AI classifiers. Annotators log in, select up to 6 tasks, and label texts one by one.

- **Backend**: Python (FastAPI, SQLAlchemy async, fastapi-users, Pydantic v2)
- **Frontend**: Quasar v2 (Vue 3 Composition API, TypeScript, Pinia, Axios)
- **Database**: SQLite (dev) / PostgreSQL (prod via `DATABASE_URL`)
- **Auth**: JWT bearer tokens via fastapi-users

---

## Repository Layout

```
backend/
  text_classifier/      Main package
    config.py           Settings from env vars
    database.py         Async SQLAlchemy engine + User table + DBError
    db_model.py         ORM models (Task, TextItem, Annotation)
    base_objects.py     Pydantic v2 request/response schemas
    crud.py             Database access functions
    routes.py           FastAPI routers (api_route, admin_route)
    main.py             App factory + middleware
    users.py            fastapi-users configuration
    prompt_parser.py    Markdown → task definition parser
  tests/                pytest test suite
  run.py                Entry-point (uvicorn)
  requirements.txt

frontend/
  src/
    pages/              One .vue file per route
    components/         Reusable UI components
    services/api.ts     Axios API wrapper (all API calls go here)
    types/api.ts        TypeScript interfaces mirroring backend schemas
    stores/             Pinia stores (one per domain: auth, tasks, annotations)
    router/routes.ts    Vue Router config

prompts/                Classification task definitions (Markdown, one per task)
logs/                   Change summaries (see below)
example.jsonl           Sample text upload file
```

---

## Running

### Backend
```bash
cd backend
pip install -r requirements.txt
python run.py          # default: http://localhost:8002
```

Key env vars (all optional):

| Variable | Default | Description |
|---|---|---|
| `DATABASE_URL` | `sqlite+aiosqlite:///database.sqlite` | SQLAlchemy async URL |
| `PRODUCTION` | `false` | When true, CORS middleware is omitted (use reverse proxy) |
| `PORT` | `8002` | uvicorn listen port |
| `ALLOWED_ORIGIN` | `http://pchradis2.fit.vutbr.cz:9005` | Allowed CORS origin in dev |
| `JWT_PRIVATE_KEY` | `supersecret` | **Change in production** |
| `SECRET` | `XYZ123…` | fastapi-users secret — **change in production** |
| `ADMIN` | `admin@example.com` | Initial superuser email |
| `ADMIN_PASSWORD` | `admin123` | **Change in production** |

### Frontend
```bash
cd frontend
npm install
npm run dev            # http://localhost:9000
npm run build          # production build → dist/spa/
```

---

## Tests

```bash
cd backend
pytest tests/
```

All new backend features must include tests. Use a temporary SQLite database for integration tests (see `tests/test_text_classifier_crud.py` for the pattern). Frontend tests: Vitest unit tests for complex store/service logic when introduced.

---

## Code Conventions

### Backend
- Python ≥ 3.11; `from __future__ import annotations` where helpful.
- Async-first: all DB calls use `AsyncSession`; no sync SQLAlchemy.
- Pydantic v2 schemas in `base_objects.py`.
- Raise `DBError` (defined in `database.py`) for database-layer failures.
- No secrets in source files — read from env via `config.py`.
- Keep routes thin: business logic in `crud.py` or service modules.

### Frontend
- Vue 3 Composition API (`<script setup>`); no Options API.
- All API types in `src/types/api.ts` must mirror backend schemas.
- API calls through `src/services/api.ts` only — no direct `axios` calls from components.
- One Pinia store per domain (auth, tasks, annotations).
- Quasar components preferred over raw HTML.

### General
- No hard-coded credentials, URLs, or file paths.
- Commits: one logical change per commit.

---

## Documentation

- Public-facing API changes must be reflected in `frontend/openapi.json` (regenerate from `/openapi.json`).
- Significant changes should update `rebuild_task.md` and/or `docs/`.
- Each classification task lives in `prompts/{task_id}.md`.

---

## Change Log

Every non-trivial change must have a log file:

```
logs/{YYYYMMDDTHHMMSS}_{short_snake_case_description}.md
```

Contents: what changed, why, decisions made. The `logs/` directory is committed.

---

## Security (OWASP Top 10)

- **A01 Broken Access Control**: Admin routes check `user.is_superuser`. User routes never expose other users' data.
- **A02 Cryptographic Failures**: `JWT_PRIVATE_KEY`, `SECRET`, `ADMIN_PASSWORD` must be strong random values in production.
- **A03 Injection**: Use SQLAlchemy ORM / parameterised queries only — never interpolate user input into SQL.
- **A05 Security Misconfiguration**: Set `PRODUCTION=true` in production; CORS middleware is then omitted (handled by reverse proxy).
- **A07 Auth Failures**: Keep JWT lifetime short in production.

---

## Task Definition Format

```json
{
  "id": "style",
  "name": "Style",
  "description_md": "# Task\n…",
  "multi_choice": true,
  "max_choices": 2,
  "enabled": true,
  "classes": [
    {"id": "formal", "label_en": "Formal", "label_cs": "formální"}
  ]
}
```

Upload via `POST /api/admin/tasks` or use the Admin page import button.

---

## Text Upload Format (JSONL)

Required fields per line:

| Field | Type | Notes |
|---|---|---|
| `id` | string | Unique text identifier; duplicates are upserted |
| `text` | string | Passage shown to annotators |
| `language` | string | ISO 639-3 code (e.g. `ces`, `eng`) |

All other fields are stored as raw JSON for export and benchmarking.

---

## Key Design Decisions

| Decision | Choice | Reason |
|---|---|---|
| Task selection UX | User picks ≤ 6 tasks; texts served one-by-one | Manageable cognitive load |
| Task storage | DB (parsed from `.md` → JSON → uploaded) | Runtime admin control |
| Text storage | Full JSON blob + extracted fields | Preserves AI labels for benchmarking |
| Duplicate upload | Upsert by `id` | Safe re-import |
| Registration | Open | Low friction for annotators |
