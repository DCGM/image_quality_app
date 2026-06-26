# IMAGE_QUALITY_REBUILD_PLAN.md

## Overview

Rebuild the text-annotation app into an image-quality rating app supporting two task types:
1. **2-Forced Choice (2FC)**: Show a pair of images from a group; user picks the "better" one.
2. **Single Image Rating**: Show one image; user selects from a small fixed set of options.

**Tech stack preserved:** FastAPI + SQLAlchemy async + Quasar v2 / Vue 3 + Pinia + JWT auth.
**Package name:** `image_rater` (replaces `text_classifier`).

---

## Key Decisions

| Decision | Choice |
|---|---|
| Image storage | Local filesystem under `static/images/{task_id}/`, served as FastAPI `StaticFiles` |
| Image auth | Not required — images are public via static mount |
| Image upload | ZIP archive; groups by filename prefix (text before last `_` or `-` before digits+ext) |
| Pair-selection algorithm | Admin-configurable per task: `least_seen`, `swiss`, or `bradley_terry` |
| Reliability | Both within-user consistency (re-shows) AND inter-rater agreement |
| Bonuses | `bonus_multiplier` float on each task (default 1.0); affects points |
| Base points | 1 point per comparison/rating, scaled by bonus_multiplier × reliability |

---

## Phase 1 — Database Models (`image_rater/db_model.py`)

### Models

**Task**
- `id` (String, PK)
- `name` (String)
- `description_md` (Text)
- `instructions_md` (Text)
- `task_type` (Enum: `two_forced_choice` / `single_rating`)
- `enabled` (Boolean, default=True)
- `pair_algorithm` (String: `least_seen`/`swiss`/`bradley_terry`; for type 1 only)
- `rating_options` (JSON array of strings; for type 2 only)
- `rating_hotkeys` (JSON array of strings; optional, for type 2)
- `bonus_multiplier` (Float, default=1.0)
- `calib_ratio` (Float, default=0.15) — fraction of shown items re-shown for reliability check

**ImageItem**
- `id` (String, PK — `{task_id}/{filename}`)
- `task_id` (String, FK → tasks.id)
- `filename` (String)
- `group_id` (String — prefix extracted from filename)
- `file_path` (String — absolute path on server)
- `suspended` (Boolean, default=False)
- `width` (Integer)
- `height` (Integer)

**ImageRanking**
- `id` (UUID, PK)
- `image_id` (String, FK → image_items.id)
- `task_id` (String, FK → tasks.id)
- `score` (Float, default=1000.0)
- `comparisons` (Integer, default=0)
- `wins` (Integer, default=0)
- `updated_at` (DateTime)
- Unique: (image_id, task_id)

**Comparison** (for 2FC)
- `id` (UUID, PK)
- `user_id` (UUID, FK → users.id)
- `task_id` (String, FK → tasks.id)
- `group_id` (String)
- `image_a_id` (String, FK → image_items.id)
- `image_b_id` (String, FK → image_items.id)
- `winner_id` (String, FK → image_items.id, nullable — null while pending)
- `start_time` (DateTime)
- `end_time` (DateTime, nullable)
- `created_at` (DateTime)
- `is_reliability_check` (Boolean, default=False)
- `points_earned` (Float, nullable)

**Rating** (for single-image)
- `id` (UUID, PK)
- `user_id` (UUID, FK → users.id)
- `task_id` (String, FK → tasks.id)
- `image_id` (String, FK → image_items.id)
- `selected_option` (String, nullable — null while pending)
- `start_time` (DateTime)
- `end_time` (DateTime, nullable)
- `created_at` (DateTime)
- `is_reliability_check` (Boolean, default=False)
- `points_earned` (Float, nullable)

**UserReliability**
- `id` (UUID, PK)
- `user_id` (UUID, FK → users.id)
- `task_id` (String, FK → tasks.id)
- `consistency_score` (Float, nullable) — fraction of re-shown items answered same
- `inter_rater_agreement` (Float, nullable) — fraction matching majority vote
- `annotation_count` (Integer, default=0)
- `computed_at` (DateTime, nullable)
- Unique: (user_id, task_id)

---

## Phase 2 — Backend Services

### `image_rater/image_store.py`
- Accept ZIP bytes → extract images → save to `static/images/{task_id}/`
- Parse `group_id` from filename: everything before the last `_` or `-` followed by digits + extension
- Read image dimensions with Pillow
- Upsert `ImageItem` records

### `image_rater/pair_selector.py`
- **`least_seen`**: pick pair within group with fewest total comparisons
- **`swiss`**: pair images with similar win-loss ratios within the group
- **`bradley_terry`**: pair that maximally reduces posterior uncertainty (max Fisher information of BT model)
- Inject reliability-check re-shows at rate `task.calib_ratio`

### `image_rater/image_selector.py`
- For type 2: pick image with fewest ratings from this user; inject re-shows at `task.calib_ratio`

### `image_rater/scoring.py`
- Points formula: `floor(1 × bonus_multiplier × (0.5 + 0.5 × reliability_score))`
- Update `ImageRanking` after each comparison (Elo K=32 update or BT incremental)

### `image_rater/reliability.py`
- `consistency_score`: % of re-shown items answered identically
- `inter_rater_agreement`: % matching majority vote on same pair/image across all users

---

## Phase 3 — Pydantic Schemas (`image_rater/base_objects.py`)

- `TaskCreate`, `TaskUpdate`, `TaskRead`, `TaskStatePatch`, `TaskBonusPatch`
- `ImageItemResponse`, `ImageListResponse`
- `NextPairResponse` (image_a_url, image_b_url, pair_token, is_reliability_check)
- `NextImageResponse` (image_url, image_id, is_reliability_check)
- `ComparisonSubmit` (task_id, image_a_id, image_b_id, winner_id, start_time, end_time)
- `RatingSubmit` (task_id, image_id, selected_option, start_time, end_time)
- `LeaderboardEntry`, `MyStats`, `GlobalStats`
- `UserReliabilityResponse`

---

## Phase 4 — API Routes (`image_rater/routes.py`)

### Public
- `GET /api/tasks` — list enabled tasks
- `GET /api/tasks/{task_id}` — task definition
- `POST /api/tasks/{task_id}/next-pair` — get next pair (2FC)
- `POST /api/tasks/{task_id}/next-image` — get next image (type 2)
- `POST /api/comparisons` — submit comparison result
- `POST /api/ratings` — submit rating
- `GET /api/stats/me` — own stats
- `GET /api/stats/leaderboard` — overall leaderboard
- `GET /api/stats/leaderboard/{task_id}` — per-task leaderboard

### Admin
- `GET/POST/PUT` `/api/admin/tasks` — list/create/update tasks
- `PATCH /api/admin/tasks/{task_id}` — enable/disable/delete/set-bonus
- `POST /api/admin/tasks/{task_id}/upload-images` — upload ZIP
- `GET /api/admin/tasks/{task_id}/images` — list images
- `PATCH /api/admin/images/{image_id}` — suspend/unsuspend
- `GET /api/admin/tasks/{task_id}/rankings` — ranked image list
- `GET /api/admin/comparisons` — paginated comparison list
- `GET /api/admin/ratings` — paginated rating list
- `GET /api/admin/stats` — global stats
- `GET /api/admin/reliability` — all user reliability scores
- `POST /api/admin/reliability/recompute` — recompute all reliability

---

## Phase 5 — FastAPI App Factory (`image_rater/main.py`)

- Mount `static/` directory at `/images`
- CORS middleware (dev only)
- Auth router (fastapi-users)
- API router

---

## Phase 6 — Frontend

### Types (`src/types/api.ts`)
Mirror all backend schemas.

### API Service (`src/services/api.ts`)
One method per endpoint; no direct axios calls elsewhere.

### Stores
- `auth-store.ts` (keep as-is)
- `task-store.ts` — current task list, selected tasks
- `annotation-store.ts` — current pair/image session state

### Pages
- `LoginPage.vue` — keep
- `TaskSelectionPage.vue` — rewrite for image tasks
- `ComparisonPage.vue` — 2FC interface (side-by-side images, click/arrows)
- `RatingPage.vue` — single-image interface (image + option buttons with hotkeys)
- `LeaderboardPage.vue` — update for new schema
- `AdminPage.vue` — tabs: Tasks, Upload Images, Image Browser, Rankings, Comparisons/Ratings, Reliability
- `ErrorNotFound.vue` — keep

### Router
Update routes to new pages.

---

## Phase 7 — Tests

- `tests/test_image_store.py` — ZIP extraction, group prefix parsing
- `tests/test_pair_selector.py` — all three algorithms
- `tests/test_crud.py` — submission, scoring, duplicates
- `tests/test_routes.py` — integration tests for key endpoints

---

## Phase 8 — Cleanup

Remove:
- `text_classifier/` package
- `prompts/` directory
- `example.jsonl`, `seed_test_data.py`
- Frontend: `ClassificationPage.vue`, `example-store.ts`, `ExampleComponent.vue`, `TaskSelectionPage.vue` (rewritten fresh)
- Legacy `rebuild_task.md`, old log entries that reference text-classifier concepts
- Update `AGENTS.md`, `docs/`, `openapi.json`

---

## Points & Scoring Formula

```
points = 1 × task.bonus_multiplier × (0.5 + 0.5 × user_reliability_score)
```

Where `user_reliability_score ∈ [0, 1]` is the average of consistency_score and inter_rater_agreement (or 1.0 if not yet computed, so new users earn full points initially).

---

## Algorithm Descriptions (shown to admin)

| Algorithm | Description |
|---|---|
| `least_seen` | Shows the pair of images in the group that has been compared the fewest times. Simple and fair, ensures all pairs are seen. |
| `swiss` | Pairs images with similar win counts, like a Swiss chess tournament. Quickly separates strong from weak images. |
| `bradley_terry` | Uses a statistical model (Bradley-Terry) to pick the pair whose comparison result would most reduce uncertainty in the overall ranking. Most information-efficient but more computationally intensive. |
