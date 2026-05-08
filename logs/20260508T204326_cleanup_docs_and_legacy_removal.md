# Cleanup, docs update, and legacy removal

## What changed
- Removed deprecated legacy backend package (`backend/title_annotator`) and rating import tools.
- Removed obsolete rating-based backend tests and added a new text-classifier CRUD test.
- Updated root and frontend documentation to the new text-classification workflow.
- Regenerated `frontend/openapi.json` from the current FastAPI app.
- Fixed login redirect route from `/rating` to `/tasks`.
- Added missing `pydantic-settings` dependency required by `text_classifier.config`.

## Why
- Ensure repository matches the rebuilt architecture and AGENTS.md guidance.

## Decisions
- Kept docs concise and focused on the current workflow/endpoints only.
