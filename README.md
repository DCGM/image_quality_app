# semant_text_cl_app

Human-in-the-loop text classification app for creating benchmark labels.

## Stack
- Backend: FastAPI, SQLAlchemy async, fastapi-users, Pydantic v2
- Frontend: Quasar (Vue 3 + TypeScript)
- DB: SQLite by default (`DATABASE_URL` can point to PostgreSQL)

## Backend
```bash
cd backend
pip install -r requirements.txt
python run.py
```
Backend runs on port `8002` by default.

## Frontend
```bash
cd frontend
npm install
npm run dev
```
Frontend runs on port `9000` by default.

## Main API
- `GET /api/tasks`
- `GET /api/tasks/{task_id}`
- `POST /api/texts/next`
- `POST /api/annotations`
- `GET /api/stats/me`
- `GET /api/stats/leaderboard/{task_id}`
- `POST /api/admin/tasks`
- `PATCH /api/admin/tasks/{task_id}`
- `POST /api/admin/texts`
- `POST /api/admin/tasks/import-prompts`

## Notes
- Task definitions are stored in DB and support single-choice or multi-choice labels.
- Text uploads are JSONL; full row JSON is stored for downstream benchmarking/export.


Frontend now includes a simple admin page for importing prompt tasks and uploading JSONL texts.
