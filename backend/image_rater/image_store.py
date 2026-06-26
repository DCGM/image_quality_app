"""Extract images from a ZIP archive and register them in the database."""
from __future__ import annotations

import io
import re
import zipfile
from pathlib import Path

from PIL import Image as PilImage
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from image_rater.db_model import ImageItem, ImageRanking


def _parse_group_id(filename: str) -> str:
    """Extract group prefix from a filename.

    Rules (applied in order):
    1. Strip the file extension.
    2. Try to match ``{prefix}[_-]\\d+$`` — the group is everything before
       the last separator followed by only digits.
    3. Fall back to the bare stem if no numeric suffix is found.

    Examples::
        groupA_01.jpg  → groupA
        photo-003.png  → photo
        standalone.jpg → standalone
    """
    stem = Path(filename).stem
    m = re.match(r"^(.+)[_\-]\d+$", stem)
    return m.group(1) if m else stem


async def ingest_zip(
    db: AsyncSession,
    task_id: str,
    zip_bytes: bytes,
    static_dir: str,
) -> int:
    """Extract images from *zip_bytes*, save them to disk, and upsert DB records.

    Returns the number of images ingested.
    """
    base_dir = Path(static_dir) / "images" / task_id
    base_dir.mkdir(parents=True, exist_ok=True)

    supported = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
    count = 0

    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        for member in zf.infolist():
            if member.is_dir():
                continue
            fname = Path(member.filename).name  # strip any internal dirs
            if Path(fname).suffix.lower() not in supported:
                continue

            data = zf.read(member.filename)
            dest = base_dir / fname
            dest.write_bytes(data)

            # Read dimensions
            width: int | None = None
            height: int | None = None
            try:
                with PilImage.open(io.BytesIO(data)) as img:
                    width, height = img.size
            except Exception:
                pass

            group_id = _parse_group_id(fname)
            image_id = f"{task_id}/{fname}"

            existing = await db.get(ImageItem, image_id)
            if existing is None:
                item = ImageItem(
                    id=image_id,
                    task_id=task_id,
                    filename=fname,
                    group_id=group_id,
                    file_path=str(dest),
                    width=width,
                    height=height,
                )
                db.add(item)
                # Create ranking record
                ranking = ImageRanking(
                    image_id=image_id,
                    task_id=task_id,
                )
                db.add(ranking)
            else:
                existing.file_path = str(dest)
                existing.width = width
                existing.height = height
                existing_ranking_result = await db.execute(
                    select(ImageRanking).where(ImageRanking.image_id == image_id)
                )
                if existing_ranking_result.scalar_one_or_none() is None:
                    ranking = ImageRanking(image_id=image_id, task_id=task_id)
                    db.add(ranking)

            count += 1

    return count
