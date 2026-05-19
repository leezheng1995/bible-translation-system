---
name: claw_memory_review
description: Day 25 Memory Review + Rule Conflict Checker Skill，提供 memory policy、memory board、job memory review、dictionary/memory conflict check 與 Slack memory summary 通知。
---

# Day 25 - Claw Memory Review Skill

## Role

本 Skill 是 OpenClaw / 小龍蝦的 Memory Review 與 Rule Conflict Checker 能力層。

它不建立自製靜態網站，而是提供可被 OpenClaw Dashboard、Slack、Star-Office-UI 或未來前端串接的 memory review API。

## Scope

1. Memory policy 檢查。
2. Job memory review board。
3. Candidate memory / approved memory 檢視。
4. Dictionary / memory conflict check。
5. Slack memory summary 通知。

## API

- `GET /skills/claw/memory/policy`
- `GET /skills/claw/memory/board`
- `GET /skills/claw/memory/jobs/{job_id}/review-board`
- `POST /skills/claw/memory/conflict-check`
- `POST /skills/claw/memory/jobs/{job_id}/notify-summary`

## Policy

1. AI draft 不可直接寫入 memory。
2. AI review 不可直接寫入 memory。
3. 只有 human approved / revised translation version 才可以寫入 memory。
4. Dictionary conflict 必須在 export 前標記。
5. 本 Skill 的 conflict check 只是 deterministic pre-check，不取代人工審核。
