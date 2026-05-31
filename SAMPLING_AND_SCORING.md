# Sampling and Scoring Plan

## Current state

`get_next_text` serves the least-covered non-suspended text that the current user has not yet seen, ordered by total annotation count across the selected tasks then by text ID. There is no concept of ground truth, calibration, scoring, or inter-rater reliability.

---

## Goals

1. **Balanced sampling** — mix new texts (coverage growth) with repeated annotations (agreement measurement) and calibration texts (quality control).
2. **Points** — Elo-inspired score per annotation batch; tasks with low coverage yield higher points; agreement with other annotators gives a bonus.
3. **Calibration / ground truth (GT)** — GT texts are served periodically; users see the correct answer immediately after submitting.
4. **User reliability** — pairwise agreement, Cohen's κ, Krippendorff's α, and Dawid-Skene/MACE confusion matrices computed per (user, task) by a background job.
5. **Weighted agreement** — reliable users' votes carry higher weight when computing consensus.
6. **LLM annotations** — uploaded by admin, used only for reliability estimation, never shown in user-facing statistics.
7. **Admin IRR dashboard** — per-task and per-user reliability metrics, inferred consensus labels.

---

## 1. Database schema additions

### 1a. `Annotation` table — new columns

| Column | Type | Default | Purpose |
|---|---|---|---|
| `annotation_type` | enum `user \| ground_truth \| llm` | `user` | Source of the annotation |
| `weight` | float | `1.0` | Updated by background job based on user reliability |
| `points_earned` | float | `null` | Elo-style points awarded at submit time |

`annotation_type` lets the system exclude LLM and GT annotations from user-facing stats while including them in reliability computations.

### 1b. `UserReliability` table (new)

| Column | Type | Notes |
|---|---|---|
| `user_id` | UUID FK | |
| `task_id` | str FK | |
| `pairwise_agreement` | float | Fraction of pairings that match |
| `cohens_kappa` | float | Marginal-corrected agreement |
| `krippendorffs_alpha` | float | Handles multi-label tasks |
| `ds_sensitivity` | float | From Dawid-Skene: P(correct \| true class) diagonal mean |
| `annotation_count` | int | Count used during last computation |
| `computed_at` | datetime | Timestamp of last background recompute |

Unique constraint on `(user_id, task_id)`.

### 1c. `TaskSamplingConfig` — columns added to `Task`

| Column | Type | Default | Purpose |
|---|---|---|---|
| `calib_ratio_initial` | float | `0.30` | Calibration probability for first `calib_initial_count` annotations |
| `calib_initial_count` | int | `20` | Threshold separating "initial" from "ongoing" phase |
| `calib_ratio_ongoing` | float | `0.10` | Calibration probability after threshold |
| `repeat_probability` | float | `0.20` | Probability of serving a text already annotated by others |
| `target_coverage` | int | `3` | Soft target: annotations per text (used in point scarcity formula) |

These are admin-editable per task.

---

## 2. Sampling algorithm

`get_next_text(user_id, task_ids)` is replaced by a two-step decision:

```
For each selected task t:
    user_count[t] = number of annotations this user has submitted for t
    ratio[t] = calib_ratio_initial if user_count[t] < t.calib_initial_count
               else calib_ratio_ongoing
    needs_calib[t] = random() < ratio[t]

calib_tasks = {t for t in task_ids if needs_calib[t] and GT texts exist for t}

if calib_tasks:
    # Serve a text that has GT annotations for at least one task in calib_tasks
    # and has not been seen by this user.
    # Among eligible texts, prefer those covering the most calib_tasks.
    candidate = pick_calibration_text(user_id, calib_tasks)
    if candidate:
        return (candidate, calib_tasks_covered_by_candidate)

# Regular path
if random() < any(t.repeat_probability for t in task_ids):  # use max
    # Pick a text the user hasn't seen, that already has ≥1 annotation from others,
    # ordering by fewest annotations (closest to target coverage first).
    candidate = pick_repeat_text(user_id, task_ids)
    if candidate:
        return (candidate, [])

# Fallback: least-covered unseen text (current logic)
return (pick_new_text(user_id, task_ids), [])
```

### API response change

`POST /api/texts/next` response gains a `calibration_task_ids: list[str]` field listing which tasks have GT on this text. The frontend uses this to show calibration feedback after submit.

### Balancing across tasks

Since all selected tasks are annotated on the same text, calibration is checked per-task independently. A text is eligible as calibration if it has GT for at least one task in `calib_tasks`. After submit, the user sees feedback for each task that had GT on that text.

---

## 3. Ground truth management

### Upload

**Bulk upload**: `POST /api/admin/ground-truth` — accepts a JSONL body (same format as text annotations: `text_id`, `task_id`, `selected_classes`). All records are inserted with `annotation_type = ground_truth`.

### Mark existing annotation as GT

`PATCH /api/admin/annotations/{annotation_id}` with body `{"annotation_type": "ground_truth"}`.

### Calibration feedback

After submit, if `calibration_task_ids` is non-empty, the frontend shows a "Calibration result" panel per task:
- The submitted answer
- The GT answer
- Match / no-match indicator

This is shown immediately after clicking Submit, before the next text loads.

---

## 4. LLM annotations

`POST /api/admin/llm-annotations` — JSONL body, same fields as GT upload. All records stored with `annotation_type = llm`.

**Usage:**
- Included in reliability background job computations (treated as a high-reliability annotator).
- Excluded from all user-facing statistics (leaderboard, stats page, point computations).
- Not served to users as calibration texts (GT only).

---

## 5. Point system (Elo-inspired)

Points are computed once at submit time and stored in `Annotation.points_earned`. They are never recalculated retroactively.

### Formula

```
For each (text, task) pair in the submitted batch:

    # 1. Scarcity multiplier: tasks with low coverage award more points
    avg_coverage = total_annotations_for_task / total_texts
    scarcity = 1 + max(0, 1 - avg_coverage / task.target_coverage)
    K = 30 × scarcity          # K ∈ [30, 60]

    # 2. Expected agreement: based on user reliability (default 0.5 for new users)
    reliability = UserReliability[user, task].pairwise_agreement or 0.5
    E = reliability            # expected fraction of agreement

    # 3. Actual agreement: fraction of existing user-type annotations for this
    #    (text, task) that match the submitted answer, weighted by annotator reliability
    A = weighted_agreement(submitted_classes, existing_annotations, weights)
    # A = 1.0 if this is a GT text and matches GT answer
    # A = 0.0 if no existing annotations yet (first annotator)

    # 4. Elo delta
    delta = K × (A - E)

    # 5. Base reward for completion
    base = 1.0

    points_earned[task] = base + max(0, delta)
    # Note: negative delta reduces bonus but completion base is always earned
```

`points_earned` on the `Annotation` row stores the per-(text, task) value. Total score shown in UI is `SUM(points_earned)` per user (and per task via filter).

### Scarcity multiplier visible in UI

`GET /api/tasks` response adds `current_multiplier: float` to each task — the current scarcity value (1.0 – 2.0). Shown in the task selection dialog so users can choose high-value tasks.

---

## 6. User reliability computation (background job)

A periodic background task (e.g., every 30 minutes, triggered via FastAPI lifespan + asyncio) recomputes `UserReliability` for all (user, task) pairs that have new annotations since the last run.

### Metrics computed

All four metrics are stored:

| Metric | Library | Notes |
|---|---|---|
| Pairwise agreement | custom | Mean over all (user_a, user_b) annotation pairs on same text |
| Cohen's κ | `sklearn.metrics.cohen_kappa_score` | Marginal-corrected; for single-choice tasks |
| Krippendorff's α | `krippendorff` (pip) | Handles multi-choice; ordinal distance for ordered classes |
| Dawid-Skene | custom EM or `MACE` | Per-annotator confusion matrix + inferred consensus |

LLM annotations are included as a reference annotator. GT annotations are the "truth" column in DS when available.

### Weight update

After each reliability recompute, `Annotation.weight` is updated for all future point calculations:

```
weight = clip(reliability_score, 0.5, 2.0)
```

Past `points_earned` values are not changed.

---

## 7. Admin IRR dashboard

New tab on the Admin page: **Reliability**.

### Per-task panel

- Mean pairwise agreement across all annotator pairs
- Fleiss' κ (multi-rater extension)
- Krippendorff's α
- Distribution of Dawid-Skene inferred consensus labels

### Per-user table (per task)

| User | Annotations | Pairwise agr. | Cohen's κ | Kripp. α | DS sensitivity | Weight |
|---|---|---|---|---|---|---|

Sortable columns. Clicking a user shows their confusion matrix from Dawid-Skene.

### Inferred consensus

For texts with ≥ 2 annotations, the DS-inferred consensus label is stored (or derived on demand) and shown in the admin text browser alongside the GT label (if any).

---

## 8. Frontend changes

### Task selection dialog

Each task card gains a **point multiplier badge** (e.g., "×1.8 pts") showing `current_multiplier` and the user's own reliability for that task (if they have prior annotations).

### Leaderboard page

- Existing annotation-count columns remain.
- New column: **Score** (sum of `points_earned`).
- Leaderboard sorts by Score by default (tie-broken by annotation count).
- New column: **Reliability** (user's mean pairwise agreement across tasks).

### ClassificationPage

After submitting a text that included calibration tasks:
1. A `CalibrationFeedback` panel slides in before the next text loads.
2. For each calibration task: shows the user's answer vs. GT answer, and a match indicator.
3. "Continue" button advances to the next text.

---

## 9. New backend endpoints

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/api/admin/ground-truth` | Bulk upload GT annotations (JSONL) |
| `PATCH` | `/api/admin/annotations/{id}` | Mark annotation as GT or LLM |
| `POST` | `/api/admin/llm-annotations` | Bulk upload LLM annotations (JSONL) |
| `GET` | `/api/admin/irr` | IRR dashboard: per-task + per-user reliability |
| `POST` | `/api/admin/irr/recompute` | Trigger immediate background recompute |
| `GET` | `/api/tasks` | Extended: includes `current_multiplier` per task |
| `POST` | `/api/texts/next` | Extended response: `calibration_task_ids` |

---

## 10. Implementation phases

### Phase 1 — Schema & annotation types
- Add `annotation_type`, `weight`, `points_earned` to `Annotation`.
- Add `UserReliability` table.
- Add sampling config columns to `Task`.
- Migration: set all existing `annotation_type = user`, `weight = 1.0`.

### Phase 2 — Ground truth & LLM upload
- `POST /api/admin/ground-truth` endpoint.
- `POST /api/admin/llm-annotations` endpoint.
- `PATCH /api/admin/annotations/{id}` endpoint.
- Admin UI: GT/LLM upload tab, mark-as-GT button in annotation list.

### Phase 3 — Sampling algorithm
- Rewrite `get_next_text` with calibration + repeat logic.
- Add `calibration_task_ids` to `NextTextResponse`.
- Task sampling config editable in admin Tasks tab.

### Phase 4 — Point calculation
- Implement `compute_points_earned(user_id, text_id, task_id, submitted_classes)` in `crud.py`.
- Call at submit time in `save_annotations`.
- Add `current_multiplier` to task list endpoint.

### Phase 5 — Reliability background job
- Add `krippendorff` and `scikit-learn` to `requirements.txt`.
- Implement `compute_reliability(task_id)` function (pairwise, κ, α, DS).
- FastAPI lifespan periodic task (asyncio + asyncio.sleep loop) running every 30 min.
- `POST /api/admin/irr/recompute` for on-demand trigger.

### Phase 6 — Frontend
- Task selection dialog: multiplier badge, per-task reliability.
- Leaderboard: Score and Reliability columns.
- CalibrationFeedback panel in ClassificationPage.
- Admin Reliability tab.

---

## 11. Open questions / deferred decisions

- **Dawid-Skene implementation**: use a pure-Python EM implementation or delegate to an external library (e.g., `labelmodels`, `snorkel`). Full MACE requires iterative EM; a simplified one-pass version may suffice for the dashboard.
- **Ordered classes**: Krippendorff's α requires an ordinal distance function; for tasks without a natural order, use nominal distance (0/1). Admin should be able to set class order per task.
- **Score floor**: Whether `points_earned` can go negative (Elo allows this). Recommendation: floor at 0 per annotation to avoid demoralising new users.
- **Initial user reliability**: Default `E = 0.5`. Consider raising this slightly (e.g., 0.6) to reward early annotators more.
- **GT vs. user annotations in point formula**: GT texts use `A = 1.0 if match else 0.0` (hard signal). Regular texts use the weighted agreement of existing user-type annotations (soft signal).
