import pydantic
import datetime

# The application will work this way:
# 1. Select a random RatingRequest which was not yet rated by the user and has ratings_to_go > 0
# 3. For each title pair present to the user the chunk, the query and the two titles
# 5. User selects the better title and can mark either title as irrelevant, gibberish or wrongfully marked as irrelevant
# 6. Store the rating
# 8. Repeat from step 1


class TitleImport(pydantic.BaseModel):
    id: str                   # This is an ID of the title record
    generated_title: str
    model: str
    query: str
    prompt: str

class ChunkImport(pydantic.BaseModel):
    id: str                   # This is an ID of the chunk record
    text: str
    start_page_id: str
    from_page: int
    to_page: int
    order: int
    language: str
    vector_index: int
    document: str
    generated_titles: list[TitleImport]

class RatedTitle(TitleImport):
    preferred: bool = False
    is_irrelevant: bool = False
    is_gibberish: bool = False
    is_relevant: bool = False

class SingleRating(pydantic.BaseModel):
    titles: list[RatedTitle]
    start_time: datetime.datetime
    end_time: datetime.datetime


class RatingResponseNew(pydantic.BaseModel):
    id: str
    request_id: str
    start_time: datetime.datetime
    end_time: datetime.datetime
    ratings: list[SingleRating]


class RatingResponse(RatingResponseNew):
    user_id: str
    created_at: datetime.datetime


class RatingRequestNew(pydantic.BaseModel):
    id: str              # ID of this Rating
    chunk: ChunkImport        # The chunk to rate titles for
    titles_lists: list[list[TitleImport]]  # List of title pairs to rate
    ratings_requested: int         # Number of ratings requested
    ratings_done: int              # Number of ratings done
    ratings_to_go: int              # Number of ratings still to go


class RatingRequest(RatingRequestNew):
    created_at: datetime.datetime  # When the request was created (inserted into the DB)
