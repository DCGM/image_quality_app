#!/usr/bin/env python3
"""
Seed script for manual testing.

Usage:
    cd backend
    python seed_test_data.py [--texts N] [--db PATH]

Populates the database with:
  - 5 test annotator users  (password: "password" for all)
  - All 18 classification tasks from prompts/
  - N texts from all.768.5k.2.jsonl  (default: 120)
  - Ground-truth annotations for ~20% of texts (style, complexity, communicative_mode)
  - User annotations for all 5 users over a mix of texts and tasks
    (spread across the last 14 days to show realistic distributions)

Idempotent: re-running the script upserts records, never duplicates.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import random
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from text_classifier.base_objects import BulkAnnotationItem, TaskDefinition
from text_classifier.config import config
from text_classifier.crud import (
    bulk_upsert_annotations,
    upsert_task,
    upsert_text,
)
from text_classifier.database import Base, User
from text_classifier.db_model import Annotation, AnnotationType, Task
from text_classifier.prompt_parser import load_prompts
from fastapi_users.password import PasswordHelper

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
JSONL_FILE = ROOT / "all.768.5k.2.jsonl"
PROMPTS_DIR = ROOT.parent / "prompts"

TEST_USERS = [
    {"email": "alice@example.com",   "display_name": "Alice",   "reliability": 0.85},
    {"email": "bob@example.com",     "display_name": "Bob",     "reliability": 0.70},
    {"email": "carol@example.com",   "display_name": "Carol",   "reliability": 0.60},
    {"email": "david@example.com",   "display_name": "David",   "reliability": 0.50},
    {"email": "eve@example.com",     "display_name": "Eve",     "reliability": 0.40},
]
USER_PASSWORD = "password"

# Tasks used for GT and user annotation seeding
SEED_TASKS = ["style", "complexity", "communicative_mode"]

# Classes per task (must match what the prompts define)
TASK_CLASSES: dict[str, list[list[str]]] = {
    "style": [
        ["formal"], ["neutral"], ["informal"], ["scholarly"], ["literary"],
        ["journalistic"], ["bureaucratic"], ["didactic"],
    ],
    "complexity": [
        ["very_easy"], ["easy"], ["moderate"], ["advanced"], ["expert"],
    ],
    "communicative_mode": [
        ["narration"], ["description"], ["exposition"], ["argumentation"],
        ["record"], ["instruction"],
    ],
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
_pw = PasswordHelper()


def _random_time(days_ago_max: int = 14, days_ago_min: int = 0) -> datetime:
    offset = timedelta(
        days=random.uniform(days_ago_min, days_ago_max),
        seconds=random.randint(0, 86400),
    )
    return datetime.now(timezone.utc) - offset


def _pick_class(task_id: str, seed: int | None = None) -> list[str]:
    """Return a plausible random class for a task (seeded for reproducibility)."""
    rng = random.Random(seed)
    choices = TASK_CLASSES.get(task_id, [["uncertain"]])
    return rng.choice(choices)


def _pick_class_with_noise(
    task_id: str, ground_truth: list[str], reliability: float, noise_seed: int
) -> list[str]:
    """Return the GT class with probability=reliability, else a random wrong class."""
    rng = random.Random(noise_seed)
    if rng.random() < reliability:
        return ground_truth
    all_classes = TASK_CLASSES.get(task_id, [["uncertain"]])
    wrong = [c for c in all_classes if c != ground_truth]
    return rng.choice(wrong) if wrong else ground_truth


# ---------------------------------------------------------------------------
# User creation
# ---------------------------------------------------------------------------
async def ensure_users(db: AsyncSession) -> dict[str, uuid.UUID]:
    """Create test users if they do not exist. Returns {email: user_id}."""
    hashed_pw = _pw.hash(USER_PASSWORD)
    result: dict[str, uuid.UUID] = {}
    for spec in TEST_USERS:
        existing = (
            await db.execute(select(User).where(User.email == spec["email"]))
        ).scalar_one_or_none()
        if existing:
            result[spec["email"]] = existing.id
            print(f"  User already exists: {spec['email']} → {existing.id}")
        else:
            uid = uuid.uuid4()
            user = User(
                id=uid,
                email=spec["email"],
                display_name=spec["display_name"],
                hashed_password=hashed_pw,
                is_active=True,
                is_superuser=False,
                is_verified=True,
            )
            db.add(user)
            result[spec["email"]] = uid
            print(f"  Created user: {spec['email']} → {uid}")
    await db.commit()
    return result


# ---------------------------------------------------------------------------
# Task import
# ---------------------------------------------------------------------------
async def import_tasks(db: AsyncSession) -> list[str]:
    """Import all tasks from prompts/. Returns list of task IDs."""
    prompts = load_prompts(PROMPTS_DIR)
    for item in prompts:
        await upsert_task(db, TaskDefinition(**item))
    await db.commit()
    print(f"  Imported {len(prompts)} tasks")
    return [p["id"] for p in prompts]


# ---------------------------------------------------------------------------
# Text upload
# ---------------------------------------------------------------------------
async def upload_texts(db: AsyncSession, n: int) -> list[str]:
    """Read up to n records from the JSONL file and upsert them. Returns IDs."""
    if not JSONL_FILE.exists():
        print(f"  WARNING: {JSONL_FILE} not found — skipping text upload")
        return []
    text_ids: list[str] = []
    with JSONL_FILE.open(encoding="utf-8") as f:
        for i, line in enumerate(f):
            if i >= n:
                break
            rec = json.loads(line)
            if not all(k in rec for k in ("id", "text", "language")):
                continue
            await upsert_text(db, rec["id"], rec["text"], rec["language"], rec)
            text_ids.append(rec["id"])
    await db.commit()
    print(f"  Uploaded {len(text_ids)} texts")
    return text_ids


# ---------------------------------------------------------------------------
# Ground truth
# ---------------------------------------------------------------------------
async def seed_ground_truth(
    db: AsyncSession,
    text_ids: list[str],
    admin_id: uuid.UUID,
    gt_fraction: float = 0.20,
) -> dict[tuple[str, str], list[str]]:
    """
    Upload GT annotations for ~gt_fraction of texts, for each SEED_TASK.
    Returns {(text_id, task_id): selected_classes}.
    """
    rng = random.Random(42)
    gt_texts = rng.sample(text_ids, min(int(len(text_ids) * gt_fraction), len(text_ids)))
    gt_map: dict[tuple[str, str], list[str]] = {}
    items: list[BulkAnnotationItem] = []
    for text_id in gt_texts:
        for task_id in SEED_TASKS:
            classes = _pick_class(task_id, seed=hash(text_id + task_id) % (2**31))
            gt_map[(text_id, task_id)] = classes
            items.append(BulkAnnotationItem(
                text_id=text_id,
                task_id=task_id,
                selected_classes=classes,
            ))
    count = await bulk_upsert_annotations(db, items, AnnotationType.ground_truth, admin_id)
    await db.commit()
    print(f"  Uploaded {count} GT annotations "
          f"({len(gt_texts)} texts × {len(SEED_TASKS)} tasks)")
    return gt_map


# ---------------------------------------------------------------------------
# User annotations
# ---------------------------------------------------------------------------
async def seed_user_annotations(
    db: AsyncSession,
    user_ids: dict[str, uuid.UUID],
    text_ids: list[str],
    gt_map: dict[tuple[str, str], list[str]],
) -> None:
    """
    Insert user-type annotations for all test users.
    Each user annotates a random subset of texts; quality varies by reliability spec.
    """
    users_with_reliability = [
        (spec["email"], spec["reliability"])
        for spec in TEST_USERS
    ]

    total = 0
    for i, (email, reliability) in enumerate(users_with_reliability):
        uid = user_ids[email]
        # How many texts does this user annotate? Scale by reliability proxy.
        n_texts = int(len(text_ids) * (0.4 + reliability * 0.5))
        rng = random.Random(i * 1000)
        user_texts = rng.sample(text_ids, min(n_texts, len(text_ids)))
        user_tasks = SEED_TASKS  # all 3 tasks

        for j, text_id in enumerate(user_texts):
            for task_id in user_tasks:
                # Check if this annotation already exists
                existing = (await db.execute(
                    select(Annotation).where(
                        Annotation.user_id == uid,
                        Annotation.text_id == text_id,
                        Annotation.task_id == task_id,
                        Annotation.annotation_type == AnnotationType.user,
                    )
                )).scalar_one_or_none()
                if existing:
                    continue

                # Determine classes: agree with GT or deviate based on reliability
                gt = gt_map.get((text_id, task_id))
                if gt:
                    classes = _pick_class_with_noise(
                        task_id, gt, reliability,
                        noise_seed=hash(str(uid) + text_id + task_id) % (2**31),
                    )
                else:
                    classes = _pick_class(
                        task_id,
                        seed=hash(str(uid) + text_id + task_id) % (2**31),
                    )

                t = _random_time(days_ago_max=14)
                t_end = t + timedelta(seconds=random.randint(5, 60))
                ann = Annotation(
                    id=uuid.uuid4(),
                    user_id=uid,
                    text_id=text_id,
                    task_id=task_id,
                    selected_classes=classes,
                    start_time=t.replace(tzinfo=None),
                    end_time=t_end.replace(tzinfo=None),
                    created_at=t.replace(tzinfo=None),
                    annotation_type=AnnotationType.user,
                    weight=1.0,
                    points_earned=1.0,
                )
                db.add(ann)
                total += 1

        # Flush per user to avoid huge transactions
        await db.commit()
        print(f"  {email}: annotated {len(user_texts)} texts × {len(user_tasks)} tasks")

    print(f"  Total user annotations inserted: {total}")


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
async def print_summary(db: AsyncSession) -> None:
    from sqlalchemy import text as sql_text
    n_users = (await db.execute(sql_text("SELECT COUNT(*) FROM user"))).scalar_one()
    n_texts = (await db.execute(sql_text("SELECT COUNT(*) FROM texts"))).scalar_one()
    n_tasks = (await db.execute(sql_text("SELECT COUNT(*) FROM tasks"))).scalar_one()
    n_ann = (await db.execute(sql_text("SELECT COUNT(*) FROM annotations"))).scalar_one()
    n_gt = (await db.execute(sql_text(
        "SELECT COUNT(*) FROM annotations WHERE annotation_type='ground_truth'"
    ))).scalar_one()
    n_user_ann = (await db.execute(sql_text(
        "SELECT COUNT(*) FROM annotations WHERE annotation_type='user'"
    ))).scalar_one()
    print("\n=== Database summary ===")
    print(f"  Users:             {n_users}")
    print(f"  Tasks:             {n_tasks}")
    print(f"  Texts:             {n_texts}")
    print(f"  Annotations total: {n_ann}")
    print(f"    → user:          {n_user_ann}")
    print(f"    → ground_truth:  {n_gt}")
    print(f"\nTest user credentials: email as shown, password = '{USER_PASSWORD}'")
    print("Admin credentials:    admin@example.com / admin123 (or $ADMIN_PASSWORD)")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
async def main(n_texts: int, db_url: str) -> None:
    engine = create_async_engine(db_url, echo=False)
    Session = async_sessionmaker(engine, expire_on_commit=False)

    # Ensure schema exists
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with Session() as db:
        # Create admin if needed
        admin_existing = (
            await db.execute(select(User).where(User.email == config.ADMIN))
        ).scalar_one_or_none()
        if not admin_existing:
            admin_id = uuid.uuid4()
            db.add(User(
                id=admin_id,
                email=config.ADMIN,
                display_name="Admin",
                hashed_password=_pw.hash(config.ADMIN_PASSWORD),
                is_active=True,
                is_superuser=True,
                is_verified=True,
            ))
            await db.commit()
            print(f"  Created admin: {config.ADMIN}")
        else:
            admin_id = admin_existing.id
            print(f"  Admin exists: {config.ADMIN}")

        print("\n[1/5] Creating test users…")
        user_ids = await ensure_users(db)

        print("\n[2/5] Importing tasks from prompts/…")
        await import_tasks(db)

        print(f"\n[3/5] Uploading {n_texts} texts from {JSONL_FILE.name}…")
        text_ids = await upload_texts(db, n_texts)

        if not text_ids:
            print("No texts available — skipping annotation seeding.")
            await engine.dispose()
            return

        print(f"\n[4/5] Seeding ground-truth annotations…")
        gt_map = await seed_ground_truth(db, text_ids, admin_id)

        print(f"\n[5/5] Seeding user annotations…")
        await seed_user_annotations(db, user_ids, text_ids, gt_map)

        await print_summary(db)

    await engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed test data into the database")
    parser.add_argument(
        "--texts", type=int, default=120,
        help="Number of texts to upload from the JSONL file (default: 120)",
    )
    parser.add_argument(
        "--db", type=str, default=config.DATABASE_URL,
        help="SQLAlchemy async database URL (default: from config/env)",
    )
    args = parser.parse_args()

    print(f"Seeding database: {args.db}")
    asyncio.run(main(n_texts=args.texts, db_url=args.db))
