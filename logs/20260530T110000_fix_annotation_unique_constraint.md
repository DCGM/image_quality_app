# Fix: annotation unique constraint + frontend type updates

## What changed

### `backend/text_classifier/db_model.py`
- Changed `Annotation` unique constraint from `(user_id, text_id, task_id)` to
  `(user_id, text_id, task_id, annotation_type)`.
- Renamed the constraint to `uq_annotation_user_text_task_type`.
- This allows the same user to have one `user` annotation AND one `ground_truth`
  annotation for the same (text, task) pair — necessary for admin who both
  annotates via the UI and uploads ground-truth via the admin endpoint.

### `frontend/src/types/api.ts`
- `NextTextResponse`: added `calibration_task_ids: string[]` to match backend.
- `LeaderboardEntry`: added `score: number` and `reliability: number | null`.
- `MyStats`: added `score: number` and `per_task_score: Record<string, number>`.

### `frontend/src/pages/LeaderboardPage.vue`
- Removed unused imports: `watch` (from vue) and `TaskStats` (from api types).

## Why
- `POST /api/admin/ground-truth` was returning 500 (SQLite UNIQUE constraint
  failed) when admin had already submitted a regular annotation for the same
  text+task via the normal flow.
- Frontend types were out of sync with the backend API responses introduced in
  the sampling/scoring implementation.

## Decisions
- Chose to include `annotation_type` in the unique constraint (option 1) rather
  than introducing a synthetic GT system user. This is cleaner and more explicit.
- Database must be recreated after this migration (dev SQLite only; no ALTER TABLE
  is issued automatically).
