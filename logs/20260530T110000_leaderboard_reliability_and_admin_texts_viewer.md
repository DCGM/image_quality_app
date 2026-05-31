# Leaderboard reliability + Admin Texts annotation viewer

## What changed

### Backend (`text_classifier/crud.py`)
- **`leaderboard()`**: Now LEFT JOINs `UserReliability` on `(user_id, task_id)` to include `pairwise_agreement` as `reliability` in the returned dicts. The `GROUP BY` was extended to include the reliability column.
- **`leaderboard_overall()`**: NOW LEFT JOINs a subquery of `AVG(pairwise_agreement) GROUP BY user_id` to include an average reliability across all tasks per user.
- **`list_texts()`**: Now accepts an optional `task_id` parameter. Annotation count per text (user annotations only) is computed via a subquery and returned as `annotation_count` in each item. When `task_id` is provided the count is filtered to that task only.
- **`get_text_annotations()`**: New function — returns all annotations for a given `text_id` (optionally filtered by `task_id`), joined with `User.display_name`, serialised with `annotation_type` value, ISO timestamp, and `points_earned`.

### Backend (`text_classifier/base_objects.py`)
- **`TextItemResponse`**: Added `annotation_count: int = 0` field.
- **`TextAnnotationEntry`**: New Pydantic schema returned by the text-annotations endpoint.

### Backend (`text_classifier/routes.py`)
- **`GET /api/admin/texts`**: Added optional `task_id` query parameter passed to `list_texts`.
- **`GET /api/admin/texts/{text_id}/annotations`**: New admin-only endpoint returning `list[TextAnnotationEntry]`, with optional `task_id` filter.

### Frontend (`src/types/api.ts`)
- `TextItemResponse`: added `annotation_count: number`.
- Added `TextAnnotationEntry` interface.

### Frontend (`src/services/api.ts`)
- `getAdminTexts`: now accepts optional `taskId` which is forwarded as `task_id` query param.
- `getTextAnnotations(textId, taskId?)`: new method calling the new admin endpoint.

### Frontend (`src/pages/AdminPage.vue`)
- **Texts tab**: Added a `q-select` task filter dropdown next to the search box. Selection reloads the texts list and filters the annotation count column accordingly.
- **Texts tab**: Added `Annotations` column showing `annotation_count`.
- **Texts tab**: Added "View annotations" (list_alt icon) button per row that opens a full-screen dialog showing all annotations for that text (with columns: annotator, task, type, classes, points, date).
- Added `textAnnotationsDialog`, `textAnnotationRows`, `textAnnotationCols`, and `openTextAnnotations` handler.

## Why
- The leaderboard's `reliability` column was always showing `—` because the backend never populated it from `UserReliability`.
- The reliability bonus is already part of `_compute_points()` (using `pairwise_agreement` as the expected-accuracy baseline `E`); no code change was needed there.
- The Admin Texts tab lacked annotation counts and no way to inspect what annotators actually labelled for a given text.

## Decisions
- Leaderboard per-task: show pairwise_agreement for that specific task.
- Leaderboard overall: show average pairwise_agreement across all tasks per user.
- Annotation count in Texts tab: counts only `user` annotation type (not GT/LLM), matching the leaderboard semantics.
- The text annotations dialog does not auto-filter by the task dropdown — it shows all annotation types so admins can see GT and LLM labels too.
