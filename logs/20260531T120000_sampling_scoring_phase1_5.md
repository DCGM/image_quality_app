# Sampling & Scoring System — Phase 1–5 Implementation

## What changed

### New file: `backend/text_classifier/reliability.py`
Inter-rater reliability computation using pairwise agreement, Cohen's kappa (sklearn), and Krippendorff's alpha (krippendorff library). Called by background job and admin endpoint.

### `backend/text_classifier/db_model.py` (Phase 1)
- `AnnotationType` enum: `user`, `ground_truth`, `llm`
- `Task`: 5 new sampling config columns (`calib_ratio_initial`, `calib_initial_count`, `calib_ratio_ongoing`, `repeat_probability`, `target_coverage`)
- `Annotation`: `annotation_type` (default `user`), `weight` (default 1.0), `points_earned` (nullable)
- New `UserReliability` table: per-(user,task) reliability metrics

### `backend/text_classifier/base_objects.py` (Phase 1)
- `TaskDefinition`: 5 new sampling config fields + `current_multiplier` (computed, not stored)
- `NextTextResponse`: `calibration_task_ids: list[str]`
- New models: `BulkAnnotationItem`, `AnnotationTypeValue`, `UserReliabilityResponse`, `MyStats`
- `LeaderboardEntry`: `score: float`, `reliability: float | None`

### `backend/text_classifier/crud.py` (Phases 1–5)
- Rewrote from scratch; removed duplicate function definitions
- `upsert_task`: excludes `current_multiplier` from DB payload
- `get_next_text`: now returns `(TextItem|None, list[str])` — 3-path algorithm (calibration → repeat → new)
- `save_annotations`: now returns `{task_id: points}`, accepts `annotation_type` arg
- `leaderboard`/`leaderboard_overall`/`my_stats`: now include score
- New: `bulk_upsert_annotations`, `set_annotation_type`, `get_gt_for_text_tasks`, `get_reliability`, `get_task_multiplier`

### `backend/text_classifier/routes.py` (Phases 2–5)
- Removed all duplicate route definitions
- `POST /api/texts/next`: returns `calibration_task_ids`
- `POST /api/annotations`: returns `{"points": {task_id: float}}`
- New admin endpoints: `POST /ground-truth`, `POST /llm-annotations`, `PATCH /annotations/{id}`, `GET /irr`, `POST /irr/recompute`
- New user endpoint: `GET /api/texts/{text_id}/ground-truth`

### `backend/text_classifier/main.py` (Phase 5)
- Replaced `@on_event("startup")` with `lifespan` context manager
- Added 30-minute background reliability recomputation loop

### `backend/requirements.txt`
- Added: `krippendorff==0.8.2`, `numpy==2.4.6`, `scikit-learn==1.8.0`, `scipy==1.17.1`

### `backend/tests/test_text_classifier_crud.py`
- Fixed: `get_next_text` now returns tuple; test unpacks it

### `TASK_PROGRESS.md` (new)
Progress tracker for the sampling/scoring implementation.

## Why
To support annotation quality through calibration texts (GT), peer-agreement repeat sampling, Elo-style point scoring, and inter-rater reliability tracking.

## Decisions
- GT/LLM annotations attributed to the uploading admin's user_id to avoid creating a fake user
- Points use `max(0, A - E)` clamped at 0 so annotators never lose points
- Reliability background job skips users with <5 annotations (insufficient data)
- `ds_sensitivity` (Dawid-Skene) left as NULL for now — complex algorithm, deferred
