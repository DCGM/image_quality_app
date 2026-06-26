# Image Rater Frontend Pages & Full Integration

## What changed

Completed the full rebuild of the web application from `text_classifier` to `image_rater`.

### Frontend pages created/rewritten
- `ComparisonPage.vue` — 2-forced-choice interface, keyboard (←/→) and click support
- `RatingPage.vue` — single-image rating, configurable options with hotkey hints
- `LeaderboardPage.vue` — rewritten for new schema (comparisons/ratings stats, per-task leaderboards)
- `AdminPage.vue` — rewritten: Tasks CRUD, Image Browser (suspend/unsuspend), Rankings, Comparisons/Ratings paginated lists, Reliability viewer + recompute

### Frontend infrastructure updated
- `MainLayout.vue` — title changed to "Image Rater", nav link updated from `/classify` to `/tasks`
- `router/routes.ts` — new routes: `/tasks`, `/compare/:taskId`, `/rate/:taskId`
- `boot/axios.ts` — default API URL changed from `http://localhost:8002` to `http://localhost:8003`

### Backend bug fixes
- `image_store.py` — fixed lazy-load issue when checking for existing `ImageRanking` during upsert (used explicit `select()` instead of `db.get()` with wrong PK)
- `pair_selector.py` — fixed lazy-load on `ImageItem.ranking` by adding `selectinload(ImageItem.ranking)` to the active images query

### Cleanup
- Removed `backend/text_classifier/` (old package)
- Removed `backend/tests/test_text_classifier_crud.py`, `test_prompt_parser.py`
- Removed `backend/seed_test_data.py`, `prompts/`, `example.jsonl`
- Removed old frontend pages: `ClassificationPage.vue`, `IndexPage.vue`, `ExampleComponent.vue`, `example-store.ts`, `components/models.ts`

## Test results
- All 17 backend tests pass
- Frontend build succeeds with no errors
- Backend starts on port 8003, admin user created automatically
- Login endpoint responds correctly with JWT token
