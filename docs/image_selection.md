# Image Selection and Pair Selection

This document describes how images are chosen for annotators during a session.

---

## Groups

When a ZIP archive is uploaded for a task, every image is assigned a **group ID** derived from its filename.  The rule is:

1. Strip the file extension to get the stem (e.g. `photo-003.png` → `photo-003`).
2. If the stem ends with `[_-]<digits>`, strip the separator and the numeric suffix to get the group (e.g. `photo-003` → `photo`, `groupA_01` → `groupA`).
3. Otherwise the whole stem is the group (e.g. `standalone.jpg` → `standalone`).

Images that belong to the same group are candidates to be compared with each other in a **2-forced-choice** task.  Single-rating tasks do not use groups — images are selected independently.

---

## Two-forced-choice (2FC) tasks — pair selection

Every call to `GET /api/tasks/{task_id}/next-pair` runs the following decision tree:

```
1. With probability task.calib_ratio:
       Pick a pair the user has ALREADY seen (reliability re-check).
       → If found, return it marked is_reliability_check=True.

2. Pick a NOVEL pair (not yet seen by this user) using the task's algorithm.
       → If found, return it marked is_reliability_check=False.

3. Fall back to any pair from the task (even previously seen).
       → If found, return it marked is_reliability_check=False.

4. Return null → "All images have been compared."
```

Only **non-suspended** images are considered in steps 2–3.  In step 1, if either image of the recorded comparison has been suspended since it was first shown, that pair is silently skipped and the system falls through to step 2.

### Pair-selection algorithms

The algorithm for step 2 is configurable per task (`task.pair_algorithm`):

| Algorithm | ID | Description |
|---|---|---|
| **Least seen** | `least_seen` | Picks the unseen pair whose two members have the fewest total comparisons. Ensures every pair is covered roughly equally. |
| **Swiss** | `swiss` | Sorts images by win ratio and pairs adjacent images. Quickly separates high-quality from low-quality images within a group, like a Swiss chess tournament. |
| **Bradley-Terry** | `bradley_terry` | Uses Bradley-Terry scores (Elo-like) to compute the Fisher information for every unseen pair and picks the pair with the highest value — i.e. the pair whose result would most reduce uncertainty in the overall ranking. Most statistically efficient. |

All algorithms operate **within a group**: images from different groups are never paired together.

### Elo ranking updates

After each comparison `POST /api/tasks/{task_id}/compare`, the winner's and loser's Elo scores are updated with K=32:

```
expected_a = 1 / (1 + 10^((score_b - score_a) / 400))
score_a += 32 * (result - expected_a)   # result = 1 for win, 0 for loss
score_b += 32 * ((1 - result) - (1 - expected_a))
```

The `ImageRanking` table stores `score` (initial 1000), `comparisons`, and `wins` for each image.

---

## Single-rating tasks — image selection

Every call to `GET /api/tasks/{task_id}/next-image` runs:

```
1. With probability task.calib_ratio:
       Pick an image the user has ALREADY rated (reliability re-check).
       → If found, return it marked is_reliability_check=True.

2. Pick a NOVEL image: a random unseen non-suspended image from the task.
       → If found, return it marked is_reliability_check=False.

3. Fall back to any unsuspended image.
       → If found, return it marked is_reliability_check=False.

4. Return null → "No more images."
```

There is no group concept for single-rating tasks.

---

## Reliability re-checks (`calib_ratio`)

Both task types use `task.calib_ratio` (default 0.15) to inject **re-shows**: a fraction of sessions are used to present the same pair/image a second time to the same user.  The result is compared against the user's earlier answer to compute per-user **consistency** (fraction of re-shows answered identically).  Consistency feeds into the overall reliability score shown on the leaderboard.

---

## Summary table

| Property | 2-forced-choice | Single rating |
|---|---|---|
| Unit presented | Pair of images from the same group | Single image |
| Group enforcement | Yes — pairs always within a group | N/A |
| Novel selection algorithms | least_seen, swiss, bradley_terry | Random among unseen |
| Reliability re-check | Random previously seen pair | Random previously seen image |
| Re-check rate | `task.calib_ratio` (default 15 %) | `task.calib_ratio` (default 15 %) |
| Ranking model | Elo (K=32) | No ranking |
