from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel

from app.services.claw_memory_review_service import ClawMemoryReviewService


router = APIRouter(
    prefix="/skills/claw/memory",
    tags=["Day 25 - Memory Review + Rule Conflict Checker"],
)


class ConflictCheckRequest(BaseModel):
    job_id: Optional[str] = None
    query: Optional[str] = None
    include_dictionary: bool = True
    notify: bool = False


def service() -> ClawMemoryReviewService:
    return ClawMemoryReviewService()


@router.get("/policy")
def memory_policy():
    return service().policy()


@router.get("/board")
def memory_board(
    job_id: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = 50,
    notify: bool = False,
):
    return service().board(
        job_id=job_id,
        search=search,
        limit=limit,
        notify=notify,
    )


@router.get("/jobs/{job_id}/review-board")
def memory_review_board(job_id: str, notify: bool = False):
    return service().review_board(
        job_id=job_id,
        notify=notify,
    )


@router.post("/conflict-check")
def memory_conflict_check(req: ConflictCheckRequest):
    return service().conflict_check(
        job_id=req.job_id,
        query=req.query,
        include_dictionary=req.include_dictionary,
        notify=req.notify,
    )


@router.post("/jobs/{job_id}/notify-summary")
def memory_notify_summary(job_id: str):
    return service().notify_summary(job_id=job_id)
