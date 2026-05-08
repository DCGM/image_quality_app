# Finish rebuild for text classification app

## What changed
- Reworked backend models/schemas/routes to support final text-classification API shape with typed responses and task-state patching (enable/disable/delete).
- Added annotation validation according to single-choice vs multi-choice task configuration and max choices.
- Added next-text selection strategy based on least-covered texts for selected tasks.
- Rebuilt frontend routes/pages to text-classification flow: task selection, classification, leaderboard, and admin placeholder page.
- Replaced legacy rating API client/types with new task/text/annotation endpoints.

## Why
- Complete migration requested in `rebuild_task.md` and remove dependence on old rating workflow.

## Decisions
- Kept admin upload workflows API-driven in this pass and provided a concise admin page placeholder.
