from pydantic import BaseModel


class MismatchResponse(BaseModel):
    id: str
    request_id: str
    prompt: str
    primary_response: str
    candidate_response: str
    judge_score: float
    judge_reason: str
    timestamp: str
