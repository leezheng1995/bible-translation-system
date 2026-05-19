from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.services.claw_skill_service import ClawSkillService


router = APIRouter(prefix="/skills/claw", tags=["Day 22 - 小龍蝦 Skill / OpenClaw"])


class ScanDriveRequest(BaseModel):
    dry_run: bool = True
    notify: bool = True


class ApproveRequest(BaseModel):
    job_id: str
    segment_id: str
    reviewer: str = "Zheng"
    decision: str = Field(default="approved", description="approved / revised / rejected")
    human_notes: str = ""
    revised_text: Optional[str] = None
    auto_build_memory: bool = True
    notify: bool = True


class ArchiveRequest(BaseModel):
    job_id: str
    mark_complete: bool = False
    notify: bool = True


class SlackNotifyRequest(BaseModel):
    text: str
    channel_id: Optional[str] = None


def service() -> ClawSkillService:
    return ClawSkillService()


@router.get("/status")
def claw_status(notify: bool = False):
    return service().status(notify=notify)


@router.post("/scan-drive")
def claw_scan_drive(req: ScanDriveRequest):
    return service().scan_drive(dry_run=req.dry_run, notify=req.notify)


@router.post("/scan_drive")
def claw_scan_drive_alias(req: ScanDriveRequest):
    return service().scan_drive(dry_run=req.dry_run, notify=req.notify)


@router.get("/review-job/{job_id}")
def claw_review_job(job_id: str, notify: bool = False):
    return service().review_job(job_id=job_id, notify=notify)


@router.get("/review_job/{job_id}")
def claw_review_job_alias(job_id: str, notify: bool = False):
    return service().review_job(job_id=job_id, notify=notify)


@router.post("/approve")
def claw_approve(req: ApproveRequest):
    return service().approve(
        job_id=req.job_id,
        segment_id=req.segment_id,
        reviewer=req.reviewer,
        decision=req.decision,
        human_notes=req.human_notes,
        revised_text=req.revised_text,
        auto_build_memory=req.auto_build_memory,
        notify=req.notify,
    )


@router.post("/archive")
def claw_archive(req: ArchiveRequest):
    return service().archive(job_id=req.job_id, mark_complete=req.mark_complete, notify=req.notify)


@router.post("/slack-notify")
def claw_slack_notify(req: SlackNotifyRequest):
    return service().slack_notify(text=req.text, channel_id=req.channel_id)


@router.post("/slack_notify")
def claw_slack_notify_alias(req: SlackNotifyRequest):
    return service().slack_notify(text=req.text, channel_id=req.channel_id)
