"""Score and filter discovered questions for relevance and priority."""

import logging
import re

logger = logging.getLogger(__name__)

# High-value keywords that boost relevance score
HIGH_VALUE_KEYWORDS = {
    # Exam names (high intent)
    "ielts", "pte", "gre", "toefl", "sat", "duolingo", "celpip", "oet", "languagecert", "gmat", "d-sat",
    # Study abroad intent
    "study abroad", "study in", "admission", "university", "college",
    "mba", "ms degree", "mbbs", "masters", "undergraduate",
    # Visa intent
    "visa", "immigration", "student visa", "spouse visa",
    # Financial
    "education loan", "scholarship", "tuition",
    # Actionable question words
    "how to", "what is the best", "tips", "preparation", "coaching",
    "strategy", "score", "improve", "guide",
}

# Keywords that reduce relevance (not our domain)
NEGATIVE_KEYWORDS = {
    "quora partner program", "quora monetization", "quora spaces",
    "upvote", "follower hack", "political", "dating",
    "cryptocurrency", "bitcoin", "stock market",
    "weight loss", "diet", "medical advice",
}


def score_question(title: str, category: str, answer_count: int = 0, follower_count: int = 0) -> float:
    """Score a question from 0.0 to 1.0 based on relevance and opportunity.

    Factors:
    - Keyword relevance (how many of our target keywords appear)
    - Opportunity (fewer existing answers = better opportunity)
    - Engagement potential (more followers = more visibility)
    - Negative keyword penalty
    """
    title_lower = title.lower()
    score = 0.0

    # Keyword relevance (0-0.5)
    keyword_hits = sum(1 for kw in HIGH_VALUE_KEYWORDS if kw in title_lower)
    keyword_score = min(keyword_hits * 0.1, 0.5)
    score += keyword_score

    # Category bonus (0.1)
    if category in ("test_prep", "study_abroad", "visa"):
        score += 0.1

    # Question format bonus — questions with "how", "what", "best" are more answerable (0.1)
    question_patterns = [r"\bhow\b", r"\bwhat\b", r"\bbest\b", r"\btips\b", r"\bguide\b", r"\bprepare\b"]
    if any(re.search(p, title_lower) for p in question_patterns):
        score += 0.1

    # Opportunity score: fewer answers = better (0-0.2)
    if answer_count == 0:
        score += 0.2
    elif answer_count <= 3:
        score += 0.15
    elif answer_count <= 10:
        score += 0.05

    # Engagement potential (0-0.1)
    if follower_count >= 100:
        score += 0.1
    elif follower_count >= 10:
        score += 0.05

    # Negative keyword penalty
    for neg in NEGATIVE_KEYWORDS:
        if neg in title_lower:
            score -= 0.3

    return max(0.0, min(1.0, score))


def filter_questions(
    questions: list[dict],
    min_score: float = 0.2,
    max_results: int | None = None,
) -> list[dict]:
    """Score, filter, and sort questions by relevance.

    Args:
        questions: List of discovered question dicts
        min_score: Minimum relevance score to keep
        max_results: Maximum number of results to return

    Returns:
        Filtered and sorted list of questions with scores
    """
    scored = []
    for q in questions:
        relevance = score_question(
            title=q["title"],
            category=q.get("category", ""),
            answer_count=q.get("answer_count", 0),
            follower_count=q.get("follower_count", 0),
        )

        if relevance >= min_score:
            q["relevance_score"] = relevance
            scored.append(q)

    # Sort by score descending
    scored.sort(key=lambda x: x["relevance_score"], reverse=True)

    if max_results:
        scored = scored[:max_results]

    logger.info(f"Filtered {len(questions)} questions to {len(scored)} (min_score={min_score})")
    return scored
