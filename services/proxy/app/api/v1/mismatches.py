from fastapi import APIRouter, Depends, Query
from app.repositories.interfaces import IMismatchRepository
from app.dependencies import get_mismatch_repo

router = APIRouter()


@router.get("/mismatches")
async def get_mismatches(
    limit: int = Query(default=20, le=100),
    repo: IMismatchRepository = Depends(get_mismatch_repo),
):
    mismatches = await repo.get_recent(limit=limit)
    return {"mismatches": [m.model_dump() for m in mismatches], "count": len(mismatches)}
