---
name: claw
description: 小龍蝦 / OpenClaw agent command layer，負責人機互動指令、任務狀態、人工審核流程、Slack 通知與後續 UI/agent 對接。
---

# 小龍蝦 Skill / OpenClaw

小龍蝦 Skill 是本地聖經翻譯系統的 Agent / Skill Layer 指令入口。

核心原則：

1. 人工核准優先。
2. AI draft 不可直接寫入 Memory。
3. AI review 不可直接寫入 Memory。
4. 只有 human approved / human revised 才可觸發 Memory build。
5. 所有任務都必須可追溯、可重試。
6. bge-m3 負責 embedding / retrieval。
7. RAG 在翻譯前取回 glossary / rules / approved memories。
8. Catholic Translation Skills 必須可被 Prompt Builder / Translation Worker 套用。
9. Slack 指定頻道負責人機互動與通知，不使用 LINE，也不使用 WhatsApp。

Day 22 Endpoints：

- GET /skills/claw/status
- POST /skills/claw/scan-drive
- POST /skills/claw/scan_drive
- GET /skills/claw/review-job/{job_id}
- GET /skills/claw/review_job/{job_id}
- POST /skills/claw/approve
- POST /skills/claw/archive
- POST /skills/claw/slack-notify
- POST /skills/claw/slack_notify

Slack Config：

SLACK_BOT_TOKEN=xoxb-...
SLACK_CHANNEL_ID=C...
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/...

Never commit .env.
