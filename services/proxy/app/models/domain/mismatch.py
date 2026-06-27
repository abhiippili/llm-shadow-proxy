from pydantic import BaseModel, Field
from datetime import datetime, timezone
from uuid import uuid4


class Mismatch(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    request_id: str
    user_id: str | None = None
    prompt: str
    primary_response: str
    candidate_response: str
    judge_score: float
    judge_reason: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
