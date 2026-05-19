import json
import os
import urllib.error
import urllib.request
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from app.services.slack_notify_service import SlackNotifyService


class InternalApiClient:
    def __init__(self, base_url: Optional[str] = None) -> None:
        self.base_url = (base_url or os.getenv("CLAW_INTERNAL_BASE_URL") or "http://127.0.0.1:8000").rstrip("/")

    def get(self, path: str, timeout: int = 300) -> Dict[str, Any]:
        return self.request("GET", path, None, timeout)

    def post(self, path: str, payload: Optional[Dict[str, Any]] = None, timeout: int = 300) -> Dict[str, Any]:
        return self.request("POST", path, payload, timeout)

    def request(self, method: str, path: str, payload: Optional[Dict[str, Any]], timeout: int) -> Dict[str, Any]:
        url = self.base_url + path
        data = None
        headers = {}

        if payload is not None:
            data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            headers["Content-Type"] = "application/json"

        req = urllib.request.Request(url=url, data=data, headers=headers, method=method)

        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read().decode("utf-8")
            return json.loads(raw) if raw else {"status": "ok", "empty_body": True}
        except urllib.error.HTTPError as exc:
            return {
                "_error": True,
                "status": "error",
                "url": url,
                "status_code": exc.code,
                "body": exc.read().decode("utf-8", errors="replace"),
            }
        except Exception as exc:
            return {
                "_error": True,
                "status": "error",
                "url": url,
                "error": repr(exc),
            }


class ClawSkillService:
    def __init__(self) -> None:
        self.client = InternalApiClient()
        self.slack = SlackNotifyService()

    def status(self, notify: bool = False) -> Dict[str, Any]:
        checks = {
            "health": self.client.get("/health"),
            "db": self.client.get("/db/health"),
            "drive": self.client.get("/drive/health"),
            "model_router": self.client.get("/model-router/health"),
            "rag": self.client.get("/rag/health"),
            "memory_policy": self.client.get("/memory/policy"),
            "skills_library": self.client.get("/skills/library"),
            "catholic_dictionary": self.client.get("/skills/library/catholic-translation/dictionary"),
        }

        failed = {}
        for name, result in checks.items():
            if result.get("_error"):
                failed[name] = result
                continue
            if result.get("status") not in ("ok", None):
                failed[name] = result

        result = {
            "status": "ok" if not failed else "degraded",
            "skill": "小龍蝦 / OpenClaw",
            "version": "day22_v1",
            "time": datetime.now(timezone.utc).isoformat(),
            "internal_base_url": self.client.base_url,
            "slack": self.slack.config_status(),
            "catholic_dictionary_count": checks.get("catholic_dictionary", {}).get("count"),
            "core_principles": [
                "人工核准優先",
                "AI draft 不可直接寫入 Memory",
                "AI review 不可直接寫入 Memory",
                "只有 human approved / revised 才可 build_memory",
                "所有任務必須可追溯、可重試",
                "bge-m3 負責 embedding / retrieval",
                "RAG 在翻譯前取回 glossary / rules / approved memories",
                "Slack 指定頻道負責人機互動與通知",
            ],
            "checks": checks,
            "failed_checks": failed,
        }

        if notify:
            result["slack_notify"] = self.slack.send(
                f"OpenClaw status: {result['status']}; Catholic dictionary={result['catholic_dictionary_count']}"
            )

        return result

    def scan_drive(self, dry_run: bool = True, notify: bool = True) -> Dict[str, Any]:
        if dry_run:
            drive_tasks = self.client.get("/drive/tasks")
            result = {
                "status": "ok" if not drive_tasks.get("_error") else "error",
                "skill": "小龍蝦 / OpenClaw",
                "action": "scan_drive",
                "dry_run": True,
                "message": "Dry-run only. Listed Google Drive inbox tasks.",
                "drive_tasks": drive_tasks,
            }
            count = drive_tasks.get("count")
        else:
            discover = self.client.post("/jobs/discover-from-drive")
            result = {
                "status": "ok" if not discover.get("_error") else "error",
                "skill": "小龍蝦 / OpenClaw",
                "action": "scan_drive",
                "dry_run": False,
                "message": "Triggered job discovery from Google Drive.",
                "discover_result": discover,
            }
            count = discover.get("count") or discover.get("created_count")

        if notify:
            result["slack_notify"] = self.slack.send(f"OpenClaw scan_drive finished. dry_run={dry_run}, count={count}")

        return result

    def review_job(self, job_id: str, notify: bool = False) -> Dict[str, Any]:
        job = self.client.get(f"/jobs/{job_id}")
        files = self.client.get(f"/files/job/{job_id}")
        segments = self.client.get(f"/segments/job/{job_id}")
        translations = self.client.get(f"/translations/job/{job_id}")
        reviews = self.client.get(f"/reviews/job/{job_id}")
        human_reviews = self.client.get(f"/human-reviews/job/{job_id}")
        memories = self.client.get(f"/memory/job/{job_id}")

        result = {
            "status": "ok",
            "skill": "小龍蝦 / OpenClaw",
            "action": "review_job",
            "job_id": job_id,
            "summary": {
                "job_status": job.get("status"),
                "current_stage": job.get("current_stage"),
                "files_count": files.get("count"),
                "segments_count": segments.get("count"),
                "translation_versions_count": translations.get("versions_count"),
                "ai_reviews_count": reviews.get("count"),
                "human_reviews_count": human_reviews.get("count"),
                "memories_count": memories.get("count"),
            },
            "job": job,
            "files": files,
            "segments": segments,
            "translations": translations,
            "reviews": reviews,
            "human_reviews": human_reviews,
            "memories": memories,
        }

        if notify:
            s = result["summary"]
            result["slack_notify"] = self.slack.send(
                f"OpenClaw review_job job_id={job_id}, stage={s.get('current_stage')}, segments={s.get('segments_count')}, memories={s.get('memories_count')}"
            )

        return result

    def approve(
        self,
        job_id: str,
        segment_id: str,
        reviewer: str,
        decision: str,
        human_notes: str,
        revised_text: Optional[str] = None,
        auto_build_memory: bool = True,
        notify: bool = True,
    ) -> Dict[str, Any]:
        decision = decision.strip().lower()
        if decision not in {"approved", "revised", "rejected"}:
            return {"status": "error", "message": "decision must be approved / revised / rejected"}

        payload = {
            "reviewer": reviewer,
            "decision": decision,
            "human_notes": human_notes,
        }

        if revised_text is not None:
            payload["revised_text"] = revised_text

        submit = self.client.post(f"/human-reviews/segment/{segment_id}/submit", payload=payload)
        memory = None

        if decision in {"approved", "revised"} and auto_build_memory:
            memory = self.client.post(f"/memory/job/{job_id}/build")

        result = {
            "status": "ok" if not submit.get("_error") else "error",
            "skill": "小龍蝦 / OpenClaw",
            "action": "approve",
            "job_id": job_id,
            "segment_id": segment_id,
            "decision": decision,
            "write_policy": "Only human approved / revised can trigger memory build.",
            "submit_result": submit,
            "memory_result": memory,
        }

        if notify:
            result["slack_notify"] = self.slack.send(
                f"OpenClaw human review submitted. job_id={job_id}, segment_id={segment_id}, decision={decision}"
            )

        return result

    def archive(self, job_id: str, mark_complete: bool = False, notify: bool = True) -> Dict[str, Any]:
        before = self.client.get(f"/jobs/{job_id}")
        complete = None

        if mark_complete:
            complete = self.client.post(f"/jobs/{job_id}/complete")

        after = self.client.get(f"/jobs/{job_id}")

        result = {
            "status": "ok",
            "skill": "小龍蝦 / OpenClaw",
            "action": "archive",
            "job_id": job_id,
            "mark_complete": mark_complete,
            "message": "Day 22 archive command is available. Full Google Drive archive/export will be expanded later.",
            "job_before": before,
            "complete_result": complete,
            "job_after": after,
        }

        if notify:
            result["slack_notify"] = self.slack.send(f"OpenClaw archive executed. job_id={job_id}, mark_complete={mark_complete}")

        return result

    def slack_notify(self, text: str, channel_id: Optional[str] = None) -> Dict[str, Any]:
        return {
            "status": "ok",
            "skill": "小龍蝦 / OpenClaw",
            "action": "slack_notify",
            "slack": self.slack.send(text=text, channel_id=channel_id),
        }
