"""Health monitoring for accounts, posting pipeline, and overall system."""

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session

from src.database import AccountHealth, ActivityLog, Answer, Question, QuestionStatus, QuoraAccount

logger = logging.getLogger(__name__)


def get_system_health(db: Session) -> dict:
    """Get an overview of system health metrics."""
    now = datetime.now(timezone.utc)
    last_24h = now - timedelta(hours=24)
    last_7d = now - timedelta(days=7)

    # Account health
    accounts = db.query(QuoraAccount).all()
    account_health = {
        "total": len(accounts),
        "healthy": sum(1 for a in accounts if a.health == AccountHealth.HEALTHY),
        "warning": sum(1 for a in accounts if a.health == AccountHealth.WARNING),
        "captcha": sum(1 for a in accounts if a.health == AccountHealth.CAPTCHA),
        "banned": sum(1 for a in accounts if a.health == AccountHealth.BANNED),
        "resting": sum(1 for a in accounts if a.health == AccountHealth.RESTING),
    }

    # Question pipeline
    questions = {
        "total": db.query(func.count(Question.id)).scalar() or 0,
        "discovered": db.query(func.count(Question.id)).filter(Question.status == QuestionStatus.DISCOVERED).scalar() or 0,
        "in_review": db.query(func.count(Question.id)).filter(Question.status == QuestionStatus.REVIEW).scalar() or 0,
        "approved": db.query(func.count(Question.id)).filter(Question.status == QuestionStatus.APPROVED).scalar() or 0,
        "posted": db.query(func.count(Question.id)).filter(Question.status == QuestionStatus.POSTED).scalar() or 0,
        "rejected": db.query(func.count(Question.id)).filter(Question.status == QuestionStatus.REJECTED).scalar() or 0,
    }

    # Answer stats
    answers = {
        "total": db.query(func.count(Answer.id)).scalar() or 0,
        "drafts": db.query(func.count(Answer.id)).filter(Answer.status == "draft").scalar() or 0,
        "approved": db.query(func.count(Answer.id)).filter(Answer.status == "approved").scalar() or 0,
        "posted": db.query(func.count(Answer.id)).filter(Answer.status == "posted").scalar() or 0,
        "posted_24h": db.query(func.count(Answer.id)).filter(Answer.status == "posted", Answer.posted_at >= last_24h).scalar() or 0,
        "posted_7d": db.query(func.count(Answer.id)).filter(Answer.status == "posted", Answer.posted_at >= last_7d).scalar() or 0,
    }

    # Recent activity
    recent_failures = (
        db.query(ActivityLog)
        .filter(ActivityLog.success == False, ActivityLog.created_at >= last_24h)
        .count()
    )

    return {
        "accounts": account_health,
        "questions": questions,
        "answers": answers,
        "recent_failures_24h": recent_failures,
        "timestamp": now.isoformat(),
    }


def get_recent_activity(db: Session, limit: int = 50) -> list[dict]:
    """Get recent activity log entries."""
    entries = (
        db.query(ActivityLog)
        .order_by(ActivityLog.created_at.desc())
        .limit(limit)
        .all()
    )

    return [
        {
            "id": e.id,
            "action": e.action,
            "details": e.details,
            "success": e.success,
            "error_message": e.error_message,
            "created_at": e.created_at.isoformat() if e.created_at else None,
        }
        for e in entries
    ]


def check_alerts(db: Session) -> list[dict]:
    """Check for conditions that need human attention."""
    alerts = []

    # Check for banned accounts
    banned = db.query(QuoraAccount).filter(QuoraAccount.health == AccountHealth.BANNED).all()
    if banned:
        alerts.append({
            "level": "critical",
            "message": f"{len(banned)} account(s) appear to be banned",
            "accounts": [a.email for a in banned],
        })

    # Check for CAPTCHA blocks
    captcha = db.query(QuoraAccount).filter(QuoraAccount.health == AccountHealth.CAPTCHA).all()
    if captcha:
        alerts.append({
            "level": "warning",
            "message": f"{len(captcha)} account(s) blocked by CAPTCHA",
            "accounts": [a.email for a in captcha],
        })

    # Check if no healthy accounts are available
    healthy = db.query(QuoraAccount).filter(QuoraAccount.health == AccountHealth.HEALTHY).count()
    if healthy == 0:
        alerts.append({
            "level": "critical",
            "message": "No healthy accounts available for posting",
        })

    # Check for high failure rate in last 24 hours
    now = datetime.now(timezone.utc)
    last_24h = now - timedelta(hours=24)
    total_attempts = db.query(ActivityLog).filter(ActivityLog.action == "post_answer", ActivityLog.created_at >= last_24h).count()
    failures = db.query(ActivityLog).filter(ActivityLog.action == "post_answer", ActivityLog.success == False, ActivityLog.created_at >= last_24h).count()

    if total_attempts > 0 and failures / total_attempts > 0.3:
        alerts.append({
            "level": "warning",
            "message": f"High failure rate: {failures}/{total_attempts} posts failed in last 24h ({failures/total_attempts:.0%})",
        })

    # Check for stale review queue
    stale_reviews = db.query(Answer).filter(
        Answer.status == "draft",
        Answer.created_at <= now - timedelta(days=3),
    ).count()
    if stale_reviews > 10:
        alerts.append({
            "level": "info",
            "message": f"{stale_reviews} draft answers have been waiting for review for 3+ days",
        })

    return alerts
