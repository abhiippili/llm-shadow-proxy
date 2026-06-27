from pydantic import BaseModel


class JudgeRequest(BaseModel):
    primary_response: str
    candidate_response: str


class JudgeResponse(BaseModel):
    match: bool
    score: float
    reason: str
