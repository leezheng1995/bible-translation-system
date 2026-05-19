from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.services.claw_task_management_service import ClawTaskManagementService


router = APIRouter(
    prefix="/skills/claw/tasks",
    tags=["Day 24 - OpenClaw Task Management"],
)


class JobActionRequest(BaseModel):
    action: str = Field(description="start / retry / complete / fail / archive")
    reason: Optional[str] = None
    mark_complete: bool = False
    notify: bool = True


def service() -> ClawTaskManagementService:
    return ClawTaskManagementService()


@router.get("/board")
def task_board(
    status: Optional[str] = None,
    stage: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = 50,
    notify: bool = False,
):
    return service().task_board(
        status=status,
        stage=stage,
        search=search,
        limit=limit,
        notify=notify,
    )


@router.get("/jobs/{job_id}/summary")
def job_summary(job_id: str, notify: bool = False):
    return service().job_summary(
        job_id=job_id,
        notify=notify,
    )


@router.get("/jobs/{job_id}/review-package")
def job_review_package(job_id: str):
    return service().job_review_package(job_id=job_id)


@router.post("/jobs/{job_id}/action")
def job_action(job_id: str, req: JobActionRequest):
    return service().job_action(
        job_id=job_id,
        action=req.action,
        reason=req.reason,
        mark_complete=req.mark_complete,
        notify=req.notify,
    )


@router.post("/jobs/{job_id}/notify-summary")
def notify_job_summary(job_id: str):
    return service().job_summary(
        job_id=job_id,
        notify=True,
    )
