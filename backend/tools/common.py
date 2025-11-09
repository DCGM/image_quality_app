from collections import defaultdict
from uuid import uuid4

from title_annotator import ChunkImport, RatingRequestNew


def chunk_to_rating_request(chunk: ChunkImport, ratings_requested: int =1) -> RatingRequestNew:
    """ Take the TitleImport objects with the matching .query text use them as a single list in RatingRequestNew.titles_lists
    """

    title_lists = defaultdict(list)
    for title in chunk.generated_titles:
        title_lists[title.query].append(title)

    titles_lists = list(title_lists.values())

    rating_request = RatingRequestNew(
        id=str(uuid4()),
        chunk=chunk,
        titles_lists=titles_lists,
        ratings_requested=ratings_requested,
        ratings_done=0,
        ratings_to_go=ratings_requested
    )

    return rating_request
