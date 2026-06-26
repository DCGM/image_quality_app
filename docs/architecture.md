# image_rater Architecture

This application collects human image-quality annotations for benchmarking AI image-quality metrics.  Annotators log in, see available tasks, and label images one by one (either pairwise comparisons or single ratings).

## System context

```mermaid
flowchart LR
    A[Annotator] -->|JWT login| F[Quasar SPA]
    Admin[Administrator] -->|JWT login + superuser| F
    F -->|Axios REST calls| API[FastAPI backend]
    API -->|Async SQLAlchemy| DB[(SQLite or PostgreSQL)]
    API -->|Serve static files| FS[static/images/]
    Admin -->|Upload ZIP| F
```

## Backend responsibilities

- Authentication and user management use `fastapi-users` with JWT bearer tokens (UUID user IDs).
- Task definitions are stored in the database; each task has a type (`two_forced_choice` or `single_rating`) and configuration such as pair-selection algorithm, rating options, bonus multiplier, and reliability re-check ratio.
- Image upload accepts a ZIP archive; images are extracted to `static/images/{task_id}/`, and each image is assigned a group ID derived from its filename (see [Image Selection](image_selection.md)).
- For 2FC tasks, pair selection supports three algorithms (`least_seen`, `swiss`, `bradley_terry`); Elo scores are updated after each comparison.
- For single-rating tasks, images are served in random novel order with occasional reliability re-shows.
- A background reliability job computes per-user consistency and inter-rater agreement, which feed into the leaderboard score.

## Frontend responsibilities

- After login, users are directed to the **Task Selection** page (`/tasks`), which shows available tasks as cards.
- Selecting a 2FC task navigates to `/compare/:taskId`; selecting a rating task navigates to `/rate/:taskId`.
- The **Comparison page** shows two images side by side; the user clicks an image or presses ←/→ to choose the winner.  Points are flashed on each submission.
- The **Rating page** shows a single image with configurable option buttons (with optional keyboard hotkeys).
- The **Leaderboard page** shows the user's own stats, a weekly/all-time top-annotators table, global per-task statistics, and per-task leaderboards.
- The **Admin page** has five tabs: Tasks (CRUD), Images (browse / suspend), Rankings (Elo scores), Comparisons/Ratings (paginated history), and Reliability (per-user scores + recompute trigger).

## Annotation flow — 2FC

```mermaid
sequenceDiagram
    participant U as Annotator
    participant SPA as Quasar SPA
    participant API as FastAPI API
    participant DB as Database

    U->>SPA: Open /compare/:taskId
    SPA->>API: GET /api/tasks/{taskId}/next-pair
    API->>DB: Select pair (algorithm + reliability check)
    DB-->>API: image_a, image_b, group_id, is_reliability_check
    API-->>SPA: 200 PairResponse | 204 No Content
    U->>SPA: Click winning image
    SPA->>API: POST /api/tasks/{taskId}/compare {winner_id, loser_id, ...}
    API->>DB: Insert Comparison, update Elo scores
    API-->>SPA: 201 ComparisonResult (points earned)
    SPA->>SPA: Flash points, fetch next pair
```

## Annotation flow — Single rating

```mermaid
sequenceDiagram
    participant U as Annotator
    participant SPA as Quasar SPA
    participant API as FastAPI API
    participant DB as Database

    U->>SPA: Open /rate/:taskId
    SPA->>API: GET /api/tasks/{taskId}/next-image
    API->>DB: Select novel/reliability image
    DB-->>API: image, is_reliability_check
    API-->>SPA: 200 ImageResponse | 204 No Content
    U->>SPA: Click rating option
    SPA->>API: POST /api/tasks/{taskId}/rate {image_id, rating, ...}
    API->>DB: Insert Rating
    API-->>SPA: 201 RatingResult (points earned)
    SPA->>SPA: Fetch next image
```

## Image ingestion flow

```mermaid
sequenceDiagram
    participant Admin
    participant SPA as Admin page
    participant API as FastAPI API
    participant FS as static/images/
    participant DB as Database

    Admin->>SPA: Upload ZIP for task
    SPA->>API: POST /api/admin/tasks/{taskId}/images (multipart)
    API->>FS: Extract images to static/images/{taskId}/
    API->>DB: Upsert ImageItem + ImageRanking rows
    API-->>SPA: {"ingested": N}
```

## Key modules

| Module | Purpose |
|---|---|
| `config.py` | Pydantic settings from environment variables |
| `database.py` | Async SQLAlchemy engine, `User` ORM, `DBError` |
| `db_model.py` | ORM models: `Task`, `ImageItem`, `ImageRanking`, `Comparison`, `Rating`, `UserReliability` |
| `base_objects.py` | Pydantic v2 request/response schemas |
| `image_store.py` | ZIP extraction, group-ID parsing, image upsert |
| `pair_selector.py` | Three pair-selection algorithms + reliability re-shows |
| `image_selector.py` | Novel-image + reliability re-show selection for rating tasks |
| `scoring.py` | `compute_points()`, `update_elo()` |
| `reliability.py` | Background job: consistency + inter-rater agreement |
| `crud.py` | All database access functions |
| `routes.py` | FastAPI routers (`api_route`, `admin_route`) |
| `users.py` | fastapi-users configuration |
| `main.py` | App factory, middleware, lifespan |

## Further reading

- [Image Selection and Pair-Selection Algorithms](image_selection.md)
- [API Reference](api_reference.md)
- [Admin Guide](admin_guide.md)
