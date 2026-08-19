from pydantic import BaseModel, Field


class VocabularyAnalysisRequest(BaseModel):
    """A body of text to look for difficult words in.

    `title` is accepted because both callers send it and it reads as part of
    the note, but nothing is currently scored differently for being in it.
    """

    title: str = ""
    # The analytics page joins every note in the database into one request, so
    # this has to be generous — but not unbounded, or the request size grows
    # with the corpus forever.
    content: str = Field("", max_length=1_000_000)


class VocabularyAnalysis(BaseModel):
    total_difficult_words: int
    definitions: dict[str, str]


class VocabularyAnalysisResponse(BaseModel):
    """Wrapped in a named field because that is the shape the callers read.

    See analytics.tsx and notes/notegrid.tsx, both of which reach for
    `data.vocabulary_analysis`.
    """

    vocabulary_analysis: VocabularyAnalysis
