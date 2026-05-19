from typing import Any, Dict, List, Optional

from app.services.claw_skill_service import InternalApiClient
from app.services.slack_notify_service import SlackNotifyService


class ClawTaskManagementService:
    """
    Day 24 - OpenClaw / 小龍蝦任務管理能力。

    This service provides task-board style data for:
    - job list / filter / search
    - job summary
    - segment / translation / review inspection
    - job action entry point
    - Slack task summary notification
    """

    def __init__(self) -> None:
        self.client = InternalApiClient()
        self.slack = SlackNotifyService()

    def task_board(
        self,
        status: Optional[str] = None,
        stage: Optional[str] = None,
        search: Optional[str] = None,
        limit: int = 50,
        notify: bool = False,
    ) -> Dict[str, Any]:
        jobs_result = self.client.get("/jobs")
        jobs = jobs_result.get("jobs", []) or []

        filtered_jobs = []
        search_text = (search or "").strip().lower()
        status_filter = (status or "").strip().lower()
        stage_filter = (stage or "").strip().lower()

        for job in jobs:
            job_status = str(job.get("status") or "").lower()
            job_stage = str(job.get("current_stage") or "").lower()
            source_file_name = str(job.get("source_file_name") or "").lower()
            job_id = str(job.get("id") or "").lower()

            if status_filter and status_filter != job_status:
                continue

            if stage_filter and stage_filter != job_stage:
                continue

            if search_text:
                haystack = " ".join([job_id, source_file_name, job_status, job_stage])
                if search_text not in haystack:
                    continue

            filtered_jobs.append(job)

        filtered_jobs = filtered_jobs[: max(1, min(limit, 200))]

        board_items: List[Dict[str, Any]] = []
        for job in filtered_jobs:
            job_id = job.get("id")

            files = self.client.get(f"/files/job/{job_id}") if job_id else {}
            segments = self.client.get(f"/segments/job/{job_id}") if job_id else {}
            translations = self.client.get(f"/translations/job/{job_id}") if job_id else {}
            reviews = self.client.get(f"/reviews/job/{job_id}") if job_id else {}
            human_reviews = self.client.get(f"/human-reviews/job/{job_id}") if job_id else {}
            memories = self.client.get(f"/memory/job/{job_id}") if job_id else {}

            board_items.append(
                {
                    "job_id": job_id,
                    "source_file_name": job.get("source_file_name"),
                    "status": job.get("status"),
                    "current_stage": job.get("current_stage"),
                    "created_at": job.get("created_at"),
                    "updated_at": job.get("updated_at"),
                    "counts": {
                        "files": files.get("count"),
                        "segments": segments.get("count"),
                        "translation_versions": translations.get("versions_count"),
                        "ai_reviews": reviews.get("count"),
                        "human_reviews": human_reviews.get("count"),
                        "memories": memories.get("count"),
                    },
                }
            )

        result: Dict[str, Any] = {
            "status": "ok" if not jobs_result.get("_error") else "error",
            "skill": "claw_task_management",
            "action": "task_board",
            "filters": {
                "status": status,
                "stage": stage,
                "search": search,
                "limit": limit,
            },
            "total_jobs": len(jobs),
            "matched_jobs": len(filtered_jobs),
            "items": board_items,
        }

        if notify:
            result["slack_notify"] = self.slack.send(
                text=(
                    "🦞 Day 24 Task Board\n"
                    f"total_jobs={len(jobs)}\n"
                    f"matched_jobs={len(filtered_jobs)}\n"
                    f"filter_status={status or '-'}\n"
                    f"filter_stage={stage or '-'}"
                )
            )

        return result

    def job_summary(self, job_id: str, notify: bool = False) -> Dict[str, Any]:
        job = self.client.get(f"/jobs/{job_id}")
        files = self.client.get(f"/files/job/{job_id}")
        segments = self.client.get(f"/segments/job/{job_id}")
        translations = self.client.get(f"/translations/job/{job_id}")
        reviews = self.client.get(f"/reviews/job/{job_id}")
        human_reviews = self.client.get(f"/human-reviews/job/{job_id}")
        pending = self.client.get(f"/human-reviews/job/{job_id}/pending")
        memories = self.client.get(f"/memory/job/{job_id}")

        job_data = job.get("job", job)

        summary = {
            "job_status": job_data.get("status"),
            "current_stage": job_data.get("current_stage"),
            "source_file_name": job_data.get("source_file_name"),
            "files_count": files.get("count"),
            "segments_count": segments.get("count"),
            "translation_versions_count": translations.get("versions_count"),
            "ai_reviews_count": reviews.get("count"),
            "human_reviews_count": human_reviews.get("count"),
            "pending_human_reviews_count": pending.get("count"),
            "memories_count": memories.get("count"),
        }

        result: Dict[str, Any] = {
            "status": "ok",
            "skill": "claw_task_management",
            "action": "job_summary",
            "job_id": job_id,
            "summary": summary,
            "job": job,
        }

        if notify:
            result["slack_notify"] = self.slack.send(
                text=(
                    "🦞 Job Summary\n"
                    f"job_id={job_id}\n"
                    f"file={summary.get('source_file_name')}\n"
                    f"stage={summary.get('current_stage')}\n"
                    f"segments={summary.get('segments_count')}\n"
                    f"translations={summary.get('translation_versions_count')}\n"
                    f"ai_reviews={summary.get('ai_reviews_count')}\n"
                    f"human_reviews={summary.get('human_reviews_count')}\n"
                    f"memories={summary.get('memories_count')}"
                )
            )

        return result

    def job_review_package(self, job_id: str) -> Dict[str, Any]:
        job = self.client.get(f"/jobs/{job_id}")
        files = self.client.get(f"/files/job/{job_id}")
        segments = self.client.get(f"/segments/job/{job_id}")
        translations = self.client.get(f"/translations/job/{job_id}")
        reviews = self.client.get(f"/reviews/job/{job_id}")
        human_reviews = self.client.get(f"/human-reviews/job/{job_id}")
        pending = self.client.get(f"/human-reviews/job/{job_id}/pending")
        memories = self.client.get(f"/memory/job/{job_id}")

        segment_packages = []
        for segment in segments.get("segments", []) or []:
            segment_id = segment.get("id")
            if not segment_id:
                continue

            package = self.client.get(f"/human-reviews/segment/{segment_id}/package")
            segment_packages.append(
                {
                    "segment_id": segment_id,
                    "segment_index": segment.get("segment_index"),
                    "source_text_preview": str(segment.get("source_text") or "")[:300],
                    "package_status": package.get("status"),
                    "ai_reviews_count": package.get("package", {}).get("ai_reviews_count"),
                    "human_reviews_count": package.get("package", {}).get("human_reviews_count"),
                    "latest_translation_status": package.get("package", {}).get("latest_translation_version", {}).get("status"),
                    "package": package,
                }
            )

        return {
            "status": "ok",
            "skill": "claw_task_management",
            "action": "job_review_package",
            "job_id": job_id,
            "summary": {
                "job_status": job.get("job", job).get("status"),
                "current_stage": job.get("job", job).get("current_stage"),
                "source_file_name": job.get("job", job).get("source_file_name"),
                "files_count": files.get("count"),
                "segments_count": segments.get("count"),
                "translation_versions_count": translations.get("versions_count"),
                "ai_reviews_count": reviews.get("count"),
                "human_reviews_count": human_reviews.get("count"),
                "pending_human_reviews_count": pending.get("count"),
                "memories_count": memories.get("count"),
            },
            "job": job,
            "files": files,
            "segments": segments,
            "translations": translations,
            "reviews": reviews,
            "human_reviews": human_reviews,
            "pending": pending,
            "memories": memories,
            "segment_packages": segment_packages,
        }

    def job_action(
        self,
        job_id: str,
        action: str,
        reason: Optional[str] = None,
        mark_complete: bool = False,
        notify: bool = True,
    ) -> Dict[str, Any]:
        action = action.strip().lower()

        allowed = {
            "start": f"/jobs/{job_id}/start",
            "retry": f"/jobs/{job_id}/retry",
            "complete": f"/jobs/{job_id}/complete",
            "fail": f"/jobs/{job_id}/fail",
        }

        if action == "archive":
            archive_result = self.client.post(
                "/skills/claw/archive",
                payload={
                    "job_id": job_id,
                    "mark_complete": mark_complete,
                    "notify": notify,
                },
            )
            return {
                "status": "ok" if not archive_result.get("_error") else "error",
                "skill": "claw_task_management",
                "action": "archive",
                "job_id": job_id,
                "mark_complete": mark_complete,
                "archive_result": archive_result,
            }

        if action not in allowed:
            return {
                "status": "error",
                "message": "Unsupported action. Allowed: start, retry, complete, fail, archive",
                "job_id": job_id,
                "action": action,
            }

        payload = {}
        if reason:
            payload["reason"] = reason

        action_result = self.client.post(allowed[action], payload=payload or None)
        summary = self.job_summary(job_id=job_id, notify=False)

        result: Dict[str, Any] = {
            "status": "ok" if not action_result.get("_error") else "error",
            "skill": "claw_task_management",
            "action": action,
            "job_id": job_id,
            "reason": reason,
            "action_result": action_result,
            "summary_after_action": summary.get("summary"),
        }

        if notify:
            result["slack_notify"] = self.slack.send(
                text=(
                    "🦞 Job Action Executed\n"
                    f"job_id={job_id}\n"
                    f"action={action}\n"
                    f"status={result['status']}\n"
                    f"reason={reason or '-'}"
                )
            )

        return result
