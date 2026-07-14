from pydantic import BaseModel, Field, HttpUrl


class ExtractionRequest(BaseModel):
    url: HttpUrl
    timestamps: list[float] = Field(..., min_length=1)


class FrameResult(BaseModel):
    timestamp: float
    filename: str
    url: str


class ExtractionResponse(BaseModel):
    job_id: str
    frames: list[FrameResult]
    errors: list[str] = Field(default_factory=list)
