"""Scheduling logic for posting answers with safe rate limiting.

Ensures we don't exceed daily limits per account, maintains
human-like posting patterns, and handles account rotation.
"""

import logging
import random
from datetime import date, datetime, timezone

from sqlalchemy.orm import Session

from src.config import settings
from src.database import (
    AccountHealth,
    ActivityLog,
    Answer,
    Persona,
    Question,
    QuestionStatus,
    QuoraAccount,
)

logger = logging.getLogger(__name__)


def get_next_posting_batch(db: Session, batch_size: int = 5) -> list[dict]:
    """Get the next batch of approved answers ready for posting.

    Returns a list of dicts containing the answer, question, persona, and account
    to use for posting, respecting daily limits and account health.
    """
    today = date.today().isoformat()
    batch = []

    # Reset daily counters if it's a new day
    accounts = db.query(QuoraAccount).filter(QuoraAccount.health == AccountHealth.HEALTHY).all()
    for account in accounts:
        persona = db.query(Persona).filter(Persona.id == account.persona_id).first()
        if persona and persona.last_post_date != today:
            persona.daily_post_count = 0
            persona.last_post_date = today
            account.posts_today = 0

    db.commit()

    # Get approved answers that haven't been posted yet
    approved_answers = (
        db.query(Answer)
        .filter(Answer.status == "approved")
        .order_by(Answer.created_at.asc())
        .limit(batch_size * 2)  # Fetch extra in case some accounts are unavailable
        .all()
    )

    for answer in approved_answers:
        if len(batch) >= batch_size:
            break

        # Find a healthy account for this persona
        account = (
            db.query(QuoraAccount)
            .filter(
                QuoraAccount.persona_id == answer.persona_id,
                QuoraAccount.health == AccountHealth.HEALTHY,
                QuoraAccount.posts_today < settings.max_posts_per_account_per_day,
            )
            .first()
        )

        if not account:
            logger.warning(f"No available account for persona #{answer.persona_id} — skipping answer #{answer.id}")
            continue

        question = db.query(Question).filter(Question.id == answer.question_id).first()
        persona = db.query(Persona).filter(Persona.id == answer.persona_id).first()

        if question and persona:
            batch.append({
                "answer": answer,
                "question": question,
                "persona": persona,
                "account": account,
            })

    logger.info(f"Prepared posting batch: {len(batch)} answers")
    return batch


def calculate_post_delay() -> int:
    """Calculate a random delay between posts (in seconds).

    Uses a non-uniform distribution to mimic natural human posting patterns.
    People don't post at perfectly regular intervals.
    """
    base = random.randint(
        settings.min_delay_between_posts_seconds,
        settings.max_delay_between_posts_seconds,
    )
    # Add some extra randomness
    jitter = random.randint(-300, 600)
    return max(60, base + jitter)  # Minimum 1 minute between posts


def record_post_result(
    db: Session,
    answer: Answer,
    account: QuoraAccount,
    question: Question,
    success: bool,
    error_message: str = "",
):
    """Record the result of a posting attempt."""
    if success:
        answer.status = "posted"
        answer.posted_at = datetime.now(timezone.utc)
        question.status = QuestionStatus.POSTED
        account.posts_today += 1
        account.total_posts += 1
        account.last_active = datetime.now(timezone.utc)

        # Update persona daily count
        persona = db.query(Persona).filter(Persona.id == answer.persona_id).first()
        if persona:
            persona.daily_post_count += 1
    else:
        answer.status = "draft"  # Reset to draft so it can be retried
        question.status = QuestionStatus.APPROVED  # Reset question status

        # If the error suggests a ban or CAPTCHA, update account health
        error_lower = error_message.lower()
        if "captcha" in error_lower:
            account.health = AccountHealth.CAPTCHA
            logger.warning(f"Account {account.email} flagged with CAPTCHA")
        elif "ban" in error_lower or "suspended" in error_lower or "restricted" in error_lower:
            account.health = AccountHealth.BANNED
            logger.warning(f"Account {account.email} may be banned")

    # Log the activity
    log_entry = ActivityLog(
        action="post_answer",
        details=f"Q#{question.id} -> A#{answer.id} via {account.email}",
        persona_id=answer.persona_id,
        question_id=question.id,
        success=success,
        error_message=error_message,
    )
    db.add(log_entry)
    db.commit()
