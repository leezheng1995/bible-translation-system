import re
from collections import defaultdict
from typing import Any, Dict, List, Optional

from app.services.claw_skill_service import InternalApiClient
from app.services.slack_notify_service import SlackNotifyService


class ClawMemoryReviewService:
    """
    Day 25 - Memory Review + Rule Conflict Checker.

    Purpose:
    - Show memory policy.
    - Show memory review board by job.
    - Compare memory candidates and approved memories.
    - Detect simple conflicts between approved/candidate memories and Catholic dictionary.
    - Notify Slack with memory summary.
    """

    def __init__(self) -> None:
        self.client = InternalApiClient()
        self.slack = SlackNotifyService()

    def policy(self) -> Dict[str, Any]:
        policy = self.client.get("/memory/policy")
        return {
            "status": "ok" if not policy.get("_error") else "error",
            "skill": "claw_memory_review",
            "action": "policy",
            "policy": policy,
        }

    def board(
        self,
        job_id: Optional[str] = None,
        search: Optional[str] = None,
        limit: int = 50,
        notify: bool = False,
    ) -> Dict[str, Any]:
        jobs_result = self.client.get("/jobs")
        jobs = jobs_result.get("jobs", []) or []

        search_text = (search or "").strip().lower()
        selected_jobs = []

        for job in jobs:
            current_job_id = job.get("id")
            source_file_name = str(job.get("source_file_name") or "")
            status = str(job.get("status") or "")
            stage = str(job.get("current_stage") or "")

            if job_id and current_job_id != job_id:
                continue

            if search_text:
                haystack = " ".join([
                    str(current_job_id or ""),
                    source_file_name,
                    status,
                    stage,
                ]).lower()

                if search_text not in haystack:
                    continue

            selected_jobs.append(job)

        selected_jobs = selected_jobs[: max(1, min(limit, 200))]

        items: List[Dict[str, Any]] = []

        for job in selected_jobs:
            current_job_id = job.get("id")

            candidates = self.client.get(f"/memory/job/{current_job_id}/candidates")
            memories = self.client.get(f"/memory/job/{current_job_id}")
            human_reviews = self.client.get(f"/human-reviews/job/{current_job_id}")
            pending = self.client.get(f"/human-reviews/job/{current_job_id}/pending")
            translations = self.client.get(f"/translations/job/{current_job_id}")

            items.append(
                {
                    "job_id": current_job_id,
                    "source_file_name": job.get("source_file_name"),
                    "job_status": job.get("status"),
                    "current_stage": job.get("current_stage"),
                    "counts": {
                        "memory_candidates": self._count(candidates),
                        "approved_memories": self._count(memories),
                        "human_reviews": self._count(human_reviews),
                        "pending_human_reviews": self._count(pending),
                        "translation_versions": translations.get("versions_count"),
                    },
                    "memory_policy_status": "human_approved_only",
                }
            )

        result: Dict[str, Any] = {
            "status": "ok",
            "skill": "claw_memory_review",
            "action": "board",
            "filters": {
                "job_id": job_id,
                "search": search,
                "limit": limit,
            },
            "total_jobs": len(jobs),
            "matched_jobs": len(selected_jobs),
            "items": items,
        }

        if notify:
            result["slack_notify"] = self.slack.send(
                text=(
                    "🦞 Day 25 Memory Board\n"
                    f"total_jobs={len(jobs)}\n"
                    f"matched_jobs={len(selected_jobs)}\n"
                    f"job_id={job_id or '-'}\n"
                    "policy=human_approved_only"
                )
            )

        return result

    def review_board(self, job_id: str, notify: bool = False) -> Dict[str, Any]:
        job = self.client.get(f"/jobs/{job_id}")
        candidates = self.client.get(f"/memory/job/{job_id}/candidates")
        memories = self.client.get(f"/memory/job/{job_id}")
        human_reviews = self.client.get(f"/human-reviews/job/{job_id}")
        pending = self.client.get(f"/human-reviews/job/{job_id}/pending")
        translations = self.client.get(f"/translations/job/{job_id}")
        policy = self.client.get("/memory/policy")

        job_data = job.get("job", job)

        result: Dict[str, Any] = {
            "status": "ok",
            "skill": "claw_memory_review",
            "action": "review_board",
            "job_id": job_id,
            "summary": {
                "source_file_name": job_data.get("source_file_name"),
                "job_status": job_data.get("status"),
                "current_stage": job_data.get("current_stage"),
                "memory_candidates_count": self._count(candidates),
                "approved_memories_count": self._count(memories),
                "human_reviews_count": self._count(human_reviews),
                "pending_human_reviews_count": self._count(pending),
                "translation_versions_count": translations.get("versions_count"),
            },
            "policy": policy,
            "candidates": candidates,
            "approved_memories": memories,
            "human_reviews": human_reviews,
            "pending_human_reviews": pending,
            "translations": translations,
            "decision_rules": [
                "AI draft translations cannot be written into memory directly.",
                "AI review output cannot be written into memory directly.",
                "Only human approved / revised translation versions can become memory.",
                "Each memory must preserve source_id pointing to approved translation_version.",
                "Dictionary conflicts must be flagged before final export.",
            ],
        }

        if notify:
            s = result["summary"]
            result["slack_notify"] = self.slack.send(
                text=(
                    "🦞 Memory Review Board\n"
                    f"job_id={job_id}\n"
                    f"file={s.get('source_file_name')}\n"
                    f"stage={s.get('current_stage')}\n"
                    f"candidates={s.get('memory_candidates_count')}\n"
                    f"approved_memories={s.get('approved_memories_count')}\n"
                    f"human_reviews={s.get('human_reviews_count')}\n"
                    "policy=human_approved_only"
                )
            )

        return result

    def conflict_check(
        self,
        job_id: Optional[str] = None,
        query: Optional[str] = None,
        include_dictionary: bool = True,
        notify: bool = False,
    ) -> Dict[str, Any]:
        policy = self.client.get("/memory/policy")

        memory_sources: List[Dict[str, Any]] = []

        if job_id:
            memory_sources.append(
                {
                    "source_name": "approved_memories",
                    "payload": self.client.get(f"/memory/job/{job_id}"),
                }
            )
            memory_sources.append(
                {
                    "source_name": "memory_candidates",
                    "payload": self.client.get(f"/memory/job/{job_id}/candidates"),
                }
            )
        else:
            memory_sources.append(
                {
                    "source_name": "all_memories",
                    "payload": self.client.get("/memory"),
                }
            )

        records = []
        for source in memory_sources:
            records.extend(
                self._extract_records(
                    source_name=source["source_name"],
                    payload=source["payload"],
                )
            )

        query_text = (query or "").strip().lower()
        if query_text:
            records = [
                r for r in records
                if query_text in (r.get("source_text", "") + " " + r.get("target_text", "")).lower()
            ]

        same_source_map: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        for record in records:
            key = self._normalize(record.get("source_text"))
            if key:
                same_source_map[key].append(record)

        possible_conflicts = []
        for key, group in same_source_map.items():
            targets = {
                self._normalize(x.get("target_text"))
                for x in group
                if self._normalize(x.get("target_text"))
            }

            if len(targets) > 1:
                possible_conflicts.append(
                    {
                        "type": "same_source_multiple_targets",
                        "normalized_source": key,
                        "targets_count": len(targets),
                        "records": group,
                    }
                )

        dictionary_issues = []
        dictionary_payload = None

        if include_dictionary:
            dictionary_payload = self.client.get("/skills/library/catholic-translation/dictionary")
            entries = dictionary_payload.get("entries", []) or []

            for record in records:
                source_text = record.get("source_text", "") or ""
                target_text = record.get("target_text", "") or ""

                for entry in entries:
                    source_term = entry.get("source")
                    target_term = entry.get("target")

                    if not source_term or not target_term:
                        continue

                    if source_term.lower() in source_text.lower() and target_term not in target_text:
                        dictionary_issues.append(
                            {
                                "type": "dictionary_target_missing",
                                "source_term": source_term,
                                "expected_target": target_term,
                                "record": record,
                            }
                        )

        result: Dict[str, Any] = {
            "status": "ok",
            "skill": "claw_memory_review",
            "action": "conflict_check",
            "job_id": job_id,
            "query": query,
            "policy_name": policy.get("policy_name"),
            "records_checked": len(records),
            "possible_conflicts_count": len(possible_conflicts),
            "dictionary_issues_count": len(dictionary_issues),
            "possible_conflicts": possible_conflicts[:50],
            "dictionary_issues": dictionary_issues[:50],
            "dictionary_count": dictionary_payload.get("count") if dictionary_payload else None,
            "notes": [
                "This is a deterministic pre-check.",
                "It does not replace human review.",
                "Dictionary conflicts should be reviewed before export.",
            ],
        }

        if notify:
            result["slack_notify"] = self.slack.send(
                text=(
                    "🦞 Memory Conflict Check\n"
                    f"job_id={job_id or '-'}\n"
                    f"records_checked={len(records)}\n"
                    f"possible_conflicts={len(possible_conflicts)}\n"
                    f"dictionary_issues={len(dictionary_issues)}"
                )
            )

        return result

    def notify_summary(self, job_id: str) -> Dict[str, Any]:
        review_board = self.review_board(job_id=job_id, notify=False)
        summary = review_board.get("summary", {})

        slack_result = self.slack.send(
            text=(
                "🦞 Day 25 Memory Summary\n"
                f"job_id={job_id}\n"
                f"file={summary.get('source_file_name')}\n"
                f"stage={summary.get('current_stage')}\n"
                f"memory_candidates={summary.get('memory_candidates_count')}\n"
                f"approved_memories={summary.get('approved_memories_count')}\n"
                f"human_reviews={summary.get('human_reviews_count')}\n"
                "policy=human_approved_only"
            )
        )

        return {
            "status": "ok",
            "skill": "claw_memory_review",
            "action": "notify_summary",
            "job_id": job_id,
            "summary": summary,
            "slack_notify": slack_result,
        }

    def _count(self, payload: Dict[str, Any]) -> int:
        for key in [
            "count",
            "total",
            "matched_jobs",
            "versions_count",
            "memories_count",
            "candidates_count",
        ]:
            value = payload.get(key)
            if isinstance(value, int):
                return value

        for key in [
            "items",
            "jobs",
            "memories",
            "candidates",
            "results",
            "entries",
            "human_reviews",
            "pending",
            "versions",
        ]:
            value = payload.get(key)
            if isinstance(value, list):
                return len(value)

        return 0

    def _extract_records(self, source_name: str, payload: Dict[str, Any]) -> List[Dict[str, Any]]:
        records: List[Dict[str, Any]] = []

        for key in [
            "memories",
            "candidates",
            "items",
            "results",
            "entries",
            "versions",
            "translation_versions",
        ]:
            value = payload.get(key)
            if isinstance(value, list):
                for item in value:
                    if isinstance(item, dict):
                        records.append(self._normalize_record(source_name, item))

        if not records and isinstance(payload, dict):
            nested_keys = ["memory", "candidate", "item", "result"]
            for key in nested_keys:
                value = payload.get(key)
                if isinstance(value, dict):
                    records.append(self._normalize_record(source_name, value))

        return records

    def _normalize_record(self, source_name: str, item: Dict[str, Any]) -> Dict[str, Any]:
        source_text = (
            item.get("source_text")
            or item.get("original_text")
            or item.get("english_text")
            or item.get("input_text")
            or item.get("source")
            or ""
        )

        target_text = (
            item.get("target_text")
            or item.get("approved_text")
            or item.get("translated_text")
            or item.get("translation_text")
            or item.get("final_text")
            or item.get("memory_text")
            or item.get("content")
            or item.get("target")
            or ""
        )

        return {
            "source_name": source_name,
            "id": item.get("id") or item.get("memory_id") or item.get("candidate_id"),
            "source_id": item.get("source_id"),
            "status": item.get("status"),
            "source_text": str(source_text or ""),
            "target_text": str(target_text or ""),
            "raw": item,
        }

    def _normalize(self, text: Optional[str]) -> str:
        text = str(text or "").strip().lower()
        text = re.sub(r"\s+", " ", text)
        return text
