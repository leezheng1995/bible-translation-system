# Day 25 - Memory Review + Rule Conflict Checker API

## Goal

Day 25 建立 Memory Review 與 Rule Conflict Checker 能力層。

這一天不做自製靜態網站，而是建立可被 OpenClaw Dashboard、Slack、Star-Office-UI 或未來前端串接的 API。

## New API

- `GET /skills/claw/memory/policy`
- `GET /skills/claw/memory/board`
- `GET /skills/claw/memory/jobs/{job_id}/review-board`
- `POST /skills/claw/memory/conflict-check`
- `POST /skills/claw/memory/jobs/{job_id}/notify-summary`

## Features

1. Memory policy review.
2. Job memory review board.
3. Candidate memory and approved memory inspection.
4. Deterministic dictionary / memory conflict check.
5. Slack memory summary notification.

## Human Approval Policy

- AI draft translations cannot be written into memory directly.
- AI review output cannot be written into memory directly.
- Human revised translations are allowed only after they become human approved.
- Every memory must preserve source_id pointing to the approved translation version.
