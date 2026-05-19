# Day 24 - OpenClaw / 小龍蝦任務管理能力

## Goal

Day 24 對應 Roadmap 的「ClawPanel 任務管理頁」。

本日不建立自製靜態網站，而是建立可被 OpenClaw Dashboard、Slack、Star-Office-UI 或未來前端串接的任務管理 API。

## New API

- `GET /skills/claw/tasks/board`
- `GET /skills/claw/tasks/jobs/{job_id}/summary`
- `GET /skills/claw/tasks/jobs/{job_id}/review-package`
- `POST /skills/claw/tasks/jobs/{job_id}/action`
- `POST /skills/claw/tasks/jobs/{job_id}/notify-summary`

## Features

1. Job list / filtering / search.
2. Job summary.
3. Segment / translation / AI review / human review inspection.
4. Archive / upload operation entry point.
5. Slack task summary notification.

## Not included

Day 24 does not implement a static ClawPanel website.

OpenClaw official dashboard remains:

- `openclaw dashboard`
- `http://127.0.0.1:18789/`

pixel-agents remains an external VS Code visualization tool under:

- `external_tools/pixel-agents`
