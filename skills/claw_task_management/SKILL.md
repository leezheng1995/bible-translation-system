---
name: claw_task_management
description: Day 24 OpenClaw / 小龍蝦任務管理 Skill，提供任務列表、篩選、搜尋、Job 摘要、Segment/Translation/Review 檢視與 Archive/Upload 操作入口。
---

# Day 24 - Claw Task Management Skill

## Role

本 Skill 是 OpenClaw / 小龍蝦的任務管理能力層，對應 Roadmap Day 24 的「ClawPanel 任務管理頁」。

它不建立自製靜態網站，而是提供可供 OpenClaw Dashboard、Slack、Star-Office-UI 或未來前端串接的 task management API。

## Scope

1. 任務列表 / 篩選 / 搜尋。
2. Job 摘要。
3. Segment / Translation / Review 檢視。
4. Archive / Upload 操作入口。
5. Slack 任務摘要通知。

## API

- `GET /skills/claw/tasks/board`
- `GET /skills/claw/tasks/jobs/{job_id}/summary`
- `GET /skills/claw/tasks/jobs/{job_id}/review-package`
- `POST /skills/claw/tasks/jobs/{job_id}/action`
- `POST /skills/claw/tasks/jobs/{job_id}/notify-summary`

## Policy

1. 不繞過人工審核。
2. 不讓 AI draft 直接寫入 memory。
3. 不讓 AI review 直接寫入 memory。
4. Archive 入口只呼叫 OpenClaw archive command。
5. Memory build 仍遵守 Day 21 policy：human approved / revised only.
