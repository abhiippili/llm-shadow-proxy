from fastapi import APIRouter
from app.models.schemas.judge import JudgeRequest, JudgeResponse
from app.services.comparison_service import compare

router = APIRouter()


@router.post("/judge", response_model=JudgeResponse)
async def judge(request: JudgeRequest):
    result = compare(request.primary_response, request.candidate_response)
    return JudgeResponse(
        match=result["match"],
        score=result["score"],
        reason=result["reason"],
    )
