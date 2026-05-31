# Seed test data script

## What changed
- Added `backend/seed_test_data.py` — a standalone, idempotent script that populates the database with realistic test data for manual testing.

## What it creates
| Category | Count | Details |
|---|---|---|
| Admin user | 1 | `admin@example.com` / `admin123` (from config) |
| Test annotators | 5 | `alice`, `bob`, `carol`, `david`, `eve` @ example.com, password `password` |
| Tasks | 18 | All tasks imported from `prompts/` |
| Texts | 120 (default) | From `backend/all.768.5k.2.jsonl` (`id`, `text`, `language` fields) |
| GT annotations | ~72 | 24 random texts × 3 tasks (`style`, `complexity`, `communicative_mode`) |
| User annotations | ~1270 | 5 users × 72–99 texts × 3 tasks, timestamps spread over 14 days |

## User reliability tiers
Users differ in annotation quality (probability of agreeing with GT):

| User | Reliability |
|---|---|
| alice@example.com | 85% |
| bob@example.com | 70% |
| carol@example.com | 60% |
| david@example.com | 50% |
| eve@example.com | 40% |

## Usage
```bash
cd backend
python seed_test_data.py              # uses default DB (database.sqlite) and 120 texts
python seed_test_data.py --texts 300  # more texts
python seed_test_data.py --db sqlite+aiosqlite:///test.sqlite  # different DB
```

The script is **idempotent** — re-running it upserts data without creating duplicates.

## Decisions
- Annotations are inserted directly into the DB (not via HTTP) so the script runs standalone without a running server.
- GT annotations use `bulk_upsert_annotations` (admin user_id as submitter).
- User annotations are inserted as ORM objects with random timestamps in the past 14 days.
- Password hashing uses `fastapi_users.password.PasswordHelper` (argon2id), same as the live app.

## Test status
- 15/15 backend tests pass
- Frontend build: 0 errors, 0 warnings
