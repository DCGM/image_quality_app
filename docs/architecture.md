# semant_text_cl_app Architecture

This application collects human text-classification annotations for benchmarking AI classifiers. Annotators choose up to six enabled tasks, receive one text at a time, and submit class selections for each selected task. Administrators import markdown prompts as editable task definitions and upload JSONL text records.

## System context

```mermaid
flowchart LR
    A[Annotator] -->|JWT login| F[Quasar SPA]
    Admin[Administrator] -->|JWT login + superuser| F
    F -->|Axios REST calls| API[FastAPI backend]
    API -->|Async SQLAlchemy| DB[(SQLite or PostgreSQL)]
    API -->|Import| P[prompts/*.md]
    Admin -->|Paste JSONL| F
```

## Backend responsibilities

- Authentication and user management use `fastapi-users` with JWT bearer tokens.
- Task definitions are stored in the database and include markdown instructions, class choices, enabled state, and single-choice or multi-choice limits.
- The prompt importer parses `prompts/*.md` into task definitions by reading the `# Classes` or `# Possible classes` section.
- Annotation validation checks that submitted class IDs are valid for the task and respect task choice limits.
- Text upload accepts JSONL rows with `id`, `text`, and `language`; all extra fields are preserved as raw JSON.

## Frontend responsibilities

- After login, users are directed to the **classification page**, which shows one task at a time with a progress bar and an always-visible summary panel listing all tasks and their current answers.
- The summary panel allows jumping to any already-answered task or the immediately next unanswered task.
- The admin page is split into three tabs: **Tasks** (browse/create/edit/delete tasks), **Import** (import `prompts/*.md`), and **Texts** (upload JSONL, browse with search/pagination, suspend/unsuspend).
- The leaderboard page shows the current user's contributions, an overall top-annotators leaderboard (weekly / all-time tabs), a global per-task statistics table, and per-task leaderboards loaded on demand.
- The navbar displays the user's `display_name` (or email if not set) and links to the classification, leaderboard, and admin pages.

## Annotation flow

```mermaid
sequenceDiagram
    participant U as Annotator
    participant SPA as Quasar SPA
    participant API as FastAPI API
    participant DB as Database

    U->>SPA: Select up to 6 tasks
    SPA->>API: POST /api/texts/next {task_ids}
    API->>DB: Find least-covered unseen non-suspended text
    DB-->>API: Text item or none
    API-->>SPA: 200 text or 204 no content
    U->>SPA: Choose classes per task
    SPA->>API: POST /api/annotations
    API->>DB: Validate tasks/classes and insert annotations
    API-->>SPA: 201 Created
```

## Admin task-editing flow

```mermaid
sequenceDiagram
    participant Admin
    participant SPA as Admin page
    participant API as FastAPI API
    participant DB as Database
    participant Prompts as prompts/*.md

    Admin->>SPA: Click import prompts
    SPA->>API: POST /api/admin/tasks/import-prompts
    API->>Prompts: Parse markdown task files
    API->>DB: Upsert task definitions
    API-->>SPA: Imported count
    SPA->>API: GET /api/admin/tasks
    API-->>SPA: All task definitions
    Admin->>SPA: Edit name, prompt, choices, limits
    SPA->>API: PUT /api/admin/tasks/{task_id}
    API->>DB: Save task definition
    API-->>SPA: 204 No Content
```
