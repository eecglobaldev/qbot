"""Discovery pipeline — orchestrates finding, scoring, and storing questions."""

import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from src.config import settings
from src.database import Question, QuestionStatus
from src.discovery.google_search import discover_questions_batch
from src.discovery.scorer import filter_questions

logger = logging.getLogger(__name__)


async def run_discovery(db: Session) -> list[Question]:
    """Run a full discovery cycle: search, score, deduplicate, and store.

    Returns:
        List of newly discovered Question objects
    """
    logger.info("Starting discovery pipeline...")

    # Step 1: Discover via Google site: search
    raw_questions = await discover_questions_batch(max_per_keyword=5)
    logger.info(f"Raw discovery: {len(raw_questions)} questions")

    # Step 2: Score and filter
    scored_questions = filter_questions(
        raw_questions,
        min_score=0.2,
        max_results=settings.max_questions_per_run,
    )
    logger.info(f"After scoring/filtering: {len(scored_questions)} questions")

    # Step 3: Deduplicate against database
    new_questions = []
    for q in scored_questions:
        existing = db.query(Question).filter(Question.url == q["url"]).first()
        if existing:
            # Update score if it improved
            if q["relevance_score"] > existing.relevance_score:
                existing.relevance_score = q["relevance_score"]
                existing.updated_at = datetime.now(timezone.utc)
            continue

        question = Question(
            url=q["url"],
            title=q["title"],
            category=q.get("category", "general"),
            topics=q.get("topics", ""),
            status=QuestionStatus.DISCOVERED,
            relevance_score=q.get("relevance_score", 0.0),
            follower_count=q.get("follower_count", 0),
            answer_count=q.get("answer_count", 0),
        )
        db.add(question)
        new_questions.append(question)

    db.commit()
    logger.info(f"Stored {len(new_questions)} new questions (skipped {len(scored_questions) - len(new_questions)} duplicates)")
    return new_questions
