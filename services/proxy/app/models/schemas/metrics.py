from pydantic import BaseModel


class MetricsResponse(BaseModel):
    total_requests: int
    total_compared: int
    matches: int
    mismatches: int
    shadow_errors: int
    match_rate_percent: float
