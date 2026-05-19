from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models import AuditLog, Rule


router = APIRouter(
    prefix="/rules",
    tags=["rules"],
)


class RuleCreateRequest(BaseModel):
    name: str = Field(..., min_length=1)
    content: str = Field(..., min_length=1)
    rule_type: str = "translation_rule"
    scope: Optional[str] = None
    priority: int = 5
    version: int = 1


class RuleUpdateRequest(BaseModel):
    content: Optional[str] = None
    rule_type: Optional[str] = None
    scope: Optional[str] = None
    priority: Optional[int] = None
    version: Optional[int] = None
    is_active: Optional[bool] = None


def rule_to_dict(rule: Rule) -> dict:
    return {
        "id": rule.id,
        "name": rule.name,
        "rule_type": rule.rule_type,
        "content": rule.content,
        "scope": rule.scope,
        "priority": rule.priority,
        "version": rule.version,
        "is_active": rule.is_active,
        "created_at": rule.created_at.isoformat() if rule.created_at else None,
        "updated_at": rule.updated_at.isoformat() if rule.updated_at else None,
    }


def add_audit_log(
    db: Session,
    event_type: str,
    stage: str,
    message: str,
    job_id: Optional[str] = None,
    payload_json: Optional[str] = None,
) -> None:
    db.add(
        AuditLog(
            job_id=job_id,
            event_type=event_type,
            stage=stage,
            message=message,
            payload_json=payload_json,
        )
    )


@router.post("")
def create_rule(
    request: RuleCreateRequest,
    db: Session = Depends(get_db),
):
    rule = Rule(
        name=request.name.strip(),
        content=request.content.strip(),
        rule_type=request.rule_type,
        scope=request.scope,
        priority=request.priority,
        version=request.version,
        is_active=True,
    )

    db.add(rule)

    add_audit_log(
        db=db,
        event_type="rule_created",
        stage="rules",
        message=f"Rule created: {request.name}",
    )

    db.commit()
    db.refresh(rule)

    return {
        "status": "ok",
        "rule": rule_to_dict(rule),
    }


@router.get("")
def list_rules(
    q: Optional[str] = Query(default=None),
    rule_type: Optional[str] = Query(default=None),
    active_only: bool = Query(default=True),
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
):
    stmt = select(Rule)

    if active_only:
        stmt = stmt.where(Rule.is_active == True)

    if q:
        like_q = f"%{q}%"
        stmt = stmt.where(
            (Rule.name.like(like_q)) |
            (Rule.content.like(like_q)) |
            (Rule.scope.like(like_q))
        )

    if rule_type:
        stmt = stmt.where(Rule.rule_type == rule_type)

    stmt = stmt.order_by(Rule.priority.asc(), Rule.name.asc()).limit(limit)

    rules = db.execute(stmt).scalars().all()

    return {
        "count": len(rules),
        "rules": [rule_to_dict(rule) for rule in rules],
    }


@router.get("/{rule_id}")
def get_rule(
    rule_id: str,
    db: Session = Depends(get_db),
):
    rule = db.get(Rule, rule_id)

    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")

    return {
        "status": "ok",
        "rule": rule_to_dict(rule),
    }


@router.put("/{rule_id}")
def update_rule(
    rule_id: str,
    request: RuleUpdateRequest,
    db: Session = Depends(get_db),
):
    rule = db.get(Rule, rule_id)

    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")

    if request.content is not None:
        rule.content = request.content.strip()
    if request.rule_type is not None:
        rule.rule_type = request.rule_type
    if request.scope is not None:
        rule.scope = request.scope
    if request.priority is not None:
        rule.priority = request.priority
    if request.version is not None:
        rule.version = request.version
    if request.is_active is not None:
        rule.is_active = request.is_active

    rule.updated_at = datetime.utcnow()

    add_audit_log(
        db=db,
        event_type="rule_updated",
        stage="rules",
        message=f"Rule updated: {rule.name}",
    )

    db.commit()
    db.refresh(rule)

    return {
        "status": "ok",
        "rule": rule_to_dict(rule),
    }


@router.delete("/{rule_id}")
def deactivate_rule(
    rule_id: str,
    db: Session = Depends(get_db),
):
    rule = db.get(Rule, rule_id)

    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")

    rule.is_active = False
    rule.updated_at = datetime.utcnow()

    add_audit_log(
        db=db,
        event_type="rule_deactivated",
        stage="rules",
        message=f"Rule deactivated: {rule.name}",
    )

    db.commit()
    db.refresh(rule)

    return {
        "status": "ok",
        "rule": rule_to_dict(rule),
    }
