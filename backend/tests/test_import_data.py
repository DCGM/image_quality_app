import sys
from pathlib import Path
# Ensure backend root directory is on sys.path for package imports
_BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

import json
import pytest
from uuid import UUID

from title_annotator.base_objects import TitleImport, ChunkImport, RatingRequestNew
from tools.common import chunk_to_rating_request


class TestChunkToRatingRequest:
    def test_groups_titles_by_query(self):
        chunk = ChunkImport(
            id="chunk-1",
            text="some text",
            start_page_id="p1",
            from_page=1,
            to_page=2,
            order=1,
            language="en",
            vector_index=0,
            document="doc-1",
            generated_titles=[
                TitleImport(id="t1", generated_title="A", model="m1", query="q1", prompt="p"),
                TitleImport(id="t2", generated_title="B", model="m1", query="q2", prompt="p"),
                TitleImport(id="t3", generated_title="C", model="m1", query="q1", prompt="p"),
            ],
        )

        rr = chunk_to_rating_request(chunk, ratings_requested=3)

        # Type and id format
        assert isinstance(rr, RatingRequestNew)
        # Valid UUID
        UUID(rr.id)

        # Chunk is passed through
        assert rr.chunk.id == chunk.id
        assert rr.chunk.text == chunk.text

        # Counters
        assert rr.ratings_requested == 3
        assert rr.ratings_done == 0
        assert rr.ratings_to_go == 3

        # Grouping by query: two groups (q1 and q2)
        assert isinstance(rr.titles_lists, list)
        assert len(rr.titles_lists) == 2

        # Each inner list must contain titles of the same query
        for lst in rr.titles_lists:
            assert len(lst) >= 1
            q = lst[0].query
            assert all(t.query == q for t in lst)

        # Content check per query (order within group preserved by construction)
        groups = {lst[0].query: [t.id for t in lst] for lst in rr.titles_lists}
        assert set(groups.keys()) == {"q1", "q2"}
        assert groups["q1"] == ["t1", "t3"]
        assert groups["q2"] == ["t2"]

        # All titles appear exactly once across groups
        flattened = [t.id for lst in rr.titles_lists for t in lst]
        assert set(flattened) == {"t1", "t2", "t3"}

    def test_empty_generated_titles(self):
        chunk = ChunkImport(
            id="chunk-empty",
            text="",
            start_page_id="p0",
            from_page=0,
            to_page=0,
            order=0,
            language="en",
            vector_index=0,
            document="doc-0",
            generated_titles=[],
        )

        rr = chunk_to_rating_request(chunk)

        assert isinstance(rr, RatingRequestNew)
        assert rr.titles_lists == []
        # Defaults
        assert rr.ratings_requested == 1
        assert rr.ratings_done == 0
        assert rr.ratings_to_go == 1

    def test_default_ratings_requested_and_uuid(self):
        # Also validates UUID is well-formed when default ratings are used
        chunk = ChunkImport(
            id="chunk-2",
            text="x",
            start_page_id="p2",
            from_page=2,
            to_page=3,
            order=2,
            language="cs",
            vector_index=5,
            document="doc-2",
            generated_titles=[
                TitleImport(id="t10", generated_title="AA", model="m2", query="qq", prompt="p")
            ],
        )

        rr = chunk_to_rating_request(chunk)

        assert rr.ratings_requested == 1
        assert rr.ratings_to_go == 1
        # UUID must parse
        UUID(rr.id)
        # Single group with the single title
        assert len(rr.titles_lists) == 1
        assert [t.id for t in rr.titles_lists[0]] == ["t10"]

    def test_process_jsonl_file(self):
        """End-to-end: load JSONL file of title rows, build a synthetic ChunkImport and transform."""
        jsonl_path = Path(__file__).parent / "test_import_data.jsonl"
        assert jsonl_path.exists(), "Fixture JSONL file missing"

        chunks: list[ChunkImport] = []
        with jsonl_path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                chunks.append(ChunkImport.model_validate_json(line))

        assert len(chunks) > 0, "No titles loaded from JSONL"

        ratings_requested = 2
        for chunk in chunks:
            rr = chunk_to_rating_request(chunk, ratings_requested=2)

            # Basic counters
            assert rr.ratings_requested == ratings_requested
            assert rr.ratings_done == 0
            assert rr.ratings_to_go == ratings_requested

            assert len(rr.titles_lists) == 6
            for group in rr.titles_lists:
                assert len(group) == 2


