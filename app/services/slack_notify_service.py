import json
import os
import urllib.error
import urllib.request
from typing import Any, Dict, Optional


class SlackNotifyService:
    def __init__(self) -> None:
        self.bot_token = os.getenv("SLACK_BOT_TOKEN", "").strip()
        self.channel_id = os.getenv("SLACK_CHANNEL_ID", "").strip()
        self.webhook_url = os.getenv("SLACK_WEBHOOK_URL", "").strip()

    def config_status(self) -> Dict[str, Any]:
        return {
            "bot_token_configured": bool(self.bot_token),
            "channel_id_configured": bool(self.channel_id),
            "webhook_configured": bool(self.webhook_url),
            "preferred_mode": "bot_token_channel" if self.bot_token and self.channel_id else "webhook_or_disabled",
        }

    def send(self, text: str, channel_id: Optional[str] = None) -> Dict[str, Any]:
        text = (text or "").strip()
        if not text:
            return {"status": "skipped", "reason": "empty_text"}

        target_channel = (channel_id or self.channel_id or "").strip()

        if self.bot_token and target_channel:
            payload = {
                "channel": target_channel,
                "text": text,
                "unfurl_links": False,
                "unfurl_media": False,
            }

            req = urllib.request.Request(
                "https://slack.com/api/chat.postMessage",
                data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                headers={
                    "Content-Type": "application/json; charset=utf-8",
                    "Authorization": f"Bearer {self.bot_token}",
                },
                method="POST",
            )

            try:
                with urllib.request.urlopen(req, timeout=20) as resp:
                    data = json.loads(resp.read().decode("utf-8"))

                if data.get("ok") is True:
                    return {
                        "status": "ok",
                        "mode": "bot_token_channel",
                        "channel_id": target_channel,
                        "ts": data.get("ts"),
                    }

                return {
                    "status": "error",
                    "mode": "bot_token_channel",
                    "channel_id": target_channel,
                    "slack_error": data.get("error"),
                    "slack_response": data,
                }
            except urllib.error.HTTPError as exc:
                return {
                    "status": "error",
                    "mode": "bot_token_channel",
                    "http_status": exc.code,
                    "body": exc.read().decode("utf-8", errors="replace"),
                }
            except Exception as exc:
                return {
                    "status": "error",
                    "mode": "bot_token_channel",
                    "error": repr(exc),
                }

        if self.webhook_url:
            payload = {"text": text}
            req = urllib.request.Request(
                self.webhook_url,
                data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                headers={"Content-Type": "application/json; charset=utf-8"},
                method="POST",
            )

            try:
                with urllib.request.urlopen(req, timeout=20) as resp:
                    body = resp.read().decode("utf-8", errors="replace")
                return {
                    "status": "ok" if body.strip().lower() == "ok" else "unknown",
                    "mode": "webhook",
                    "body": body,
                }
            except urllib.error.HTTPError as exc:
                return {
                    "status": "error",
                    "mode": "webhook",
                    "http_status": exc.code,
                    "body": exc.read().decode("utf-8", errors="replace"),
                }
            except Exception as exc:
                return {
                    "status": "error",
                    "mode": "webhook",
                    "error": repr(exc),
                }

        return {
            "status": "skipped",
            "reason": "slack_not_configured",
            "message": "Set SLACK_BOT_TOKEN + SLACK_CHANNEL_ID or SLACK_WEBHOOK_URL in .env.",
            "config": self.config_status(),
        }
