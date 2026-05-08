# Rebuild text classifier (initial concise version)

## What changed
- Added a new backend package `backend/text_classifier` and switched `backend/run.py` to start it.
- Implemented initial DB models: `tasks`, `texts`, `annotations` and basic task/text/annotation CRUD paths.
- Added new API routes under `/api` and `/api/admin` for tasks, next text fetch, annotations, stats, leaderboard, and admin uploads.

## Why
- Align repository with `rebuild_task.md` migration from title rating to human text classification.
- Provide a concise but runnable baseline that can be incrementally extended.

## Decisions
- Left legacy `title_annotator` package in place for now to minimize migration risk and keep this step focused.
- Implemented simplified text assignment (`first unannotated text`) as initial behavior before adding balancing strategy.
