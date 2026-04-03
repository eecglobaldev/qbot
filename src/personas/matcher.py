"""Match discovered questions to the best expert persona."""

import re

from sqlalchemy.orm import Session

from src.database import Persona, Question


# Keyword-to-persona mapping — maps to real EEC team member slugs
TOPIC_PERSONA_MAP: dict[str, list[str]] = {
    # Test Prep — Vikram Patel (Head of Test Prep, IELTS Band 9)
    "ielts": ["vikram-patel"],
    "pte": ["vikram-patel"],
    "pte academic": ["vikram-patel"],
    "pte core": ["vikram-patel"],
    "band score": ["vikram-patel"],
    "toefl": ["vikram-patel"],
    "gre": ["vikram-patel"],
    "sat": ["vikram-patel"],
    "d-sat": ["vikram-patel"],
    "gmat": ["vikram-patel"],
    "duolingo": ["vikram-patel"],
    "celpip": ["vikram-patel"],
    "languagecert": ["vikram-patel"],
    "oet": ["vikram-patel"],
    "english proficiency": ["vikram-patel"],
    "test preparation": ["vikram-patel"],
    "quantitative": ["vikram-patel"],
    "analytical writing": ["vikram-patel"],

    # Study in USA / Canada / UK — Priya Sharma (Senior USA Consultant, 98% visa rate)
    "study in usa": ["priya-sharma", "amit-jalan"],
    "study in canada": ["priya-sharma"],
    "study in uk": ["priya-sharma"],
    "study in the uk": ["priya-sharma"],
    "f-1 visa": ["priya-sharma"],
    "f1 visa": ["priya-sharma"],
    "sop": ["priya-sharma"],
    "statement of purpose": ["priya-sharma"],
    "lor": ["priya-sharma"],
    "university admission": ["priya-sharma", "amit-jalan"],
    "scholarship": ["priya-sharma", "madhav-gupta"],
    "mba abroad": ["priya-sharma", "amit-jalan"],
    "ms abroad": ["priya-sharma", "amit-jalan"],
    "undergraduate abroad": ["priya-sharma"],

    # Study in Europe / Germany — Rahul Mehta (Europe specialist, 2500+ students)
    "study in germany": ["rahul-mehta"],
    "study in europe": ["rahul-mehta"],
    "study in france": ["rahul-mehta"],
    "study in ireland": ["rahul-mehta"],
    "study in italy": ["rahul-mehta"],
    "study in netherlands": ["rahul-mehta"],
    "schengen": ["rahul-mehta"],
    "free tuition": ["rahul-mehta"],
    "tuition free": ["rahul-mehta"],
    "mim": ["rahul-mehta"],
    "masters in management": ["rahul-mehta"],
    "mbbs abroad": ["rahul-mehta"],
    "mbbs": ["rahul-mehta"],
    "neet": ["rahul-mehta"],

    # Study in Australia / NZ — Anita Desai + Anirudh Gupta
    "study in australia": ["anita-desai", "anirudh-gupta"],
    "study in new zealand": ["anita-desai"],
    "australia": ["anita-desai", "anirudh-gupta"],
    "subclass 500": ["anita-desai"],
    "australian pr": ["anita-desai", "anirudh-gupta"],
    "pr in australia": ["anita-desai", "anirudh-gupta"],
    "pr pathway": ["anita-desai", "anirudh-gupta"],
    "permanent residency": ["anita-desai", "anirudh-gupta"],
    "group of eight": ["anita-desai", "anirudh-gupta"],
    "go8": ["anirudh-gupta"],
    "genuine student": ["anirudh-gupta"],
    "gs requirement": ["anirudh-gupta"],
    "new zealand": ["anita-desai"],
    "bond university": ["anirudh-gupta"],

    # General study abroad — Amit Jalan (Founder)
    "study abroad": ["amit-jalan", "priya-sharma"],
    "which country": ["amit-jalan", "priya-sharma"],
    "best country": ["amit-jalan", "priya-sharma"],
    "career counseling": ["amit-jalan"],
    "career guidance": ["amit-jalan"],

    # Visa — Mohita Gupta (VP Visa Strategy, ex-Citibank)
    "visa": ["mohita-gupta"],
    "student visa": ["mohita-gupta"],
    "spouse visa": ["mohita-gupta"],
    "tourist visa": ["mohita-gupta"],
    "visa extension": ["mohita-gupta"],
    "visa interview": ["mohita-gupta", "vikram-patel"],
    "immigration": ["mohita-gupta"],
    "visa rejection": ["mohita-gupta"],
    "visa refusal": ["mohita-gupta"],
    "visa appeal": ["mohita-gupta"],

    # Education Loan & Finance — CA Madhav Gupta (Chartered Accountant)
    "education loan": ["madhav-gupta"],
    "student loan": ["madhav-gupta"],
    "loan": ["madhav-gupta"],
    "financial": ["madhav-gupta"],
    "cost of studying": ["madhav-gupta"],
    "tuition fee": ["madhav-gupta"],
    "forex": ["madhav-gupta"],
    "fund": ["madhav-gupta"],
    "budget": ["madhav-gupta"],

    # Language
    "spoken english": ["vikram-patel"],
    "french": ["rahul-mehta"],
    "german": ["rahul-mehta"],
}


def match_persona_to_question(question: Question, db: Session) -> Persona | None:
    """Find the best persona to answer a given question.

    Strategy:
    1. Check question title and topics against keyword map
    2. Score each persona by number of keyword matches
    3. Return the highest-scoring active persona
    4. Fall back to the founder (amit-jalan) for general questions
    """
    title_lower = question.title.lower()
    topics_lower = (question.topics or "").lower()
    combined_text = f"{title_lower} {topics_lower}"

    # Score each persona slug
    persona_scores: dict[str, int] = {}

    for keyword, slugs in TOPIC_PERSONA_MAP.items():
        # Use word boundary matching for short keywords to avoid false matches
        if len(keyword) <= 4:
            pattern = rf"\b{re.escape(keyword)}\b"
            if re.search(pattern, combined_text, re.IGNORECASE):
                for slug in slugs:
                    persona_scores[slug] = persona_scores.get(slug, 0) + 2
        elif keyword.lower() in combined_text:
            for slug in slugs:
                persona_scores[slug] = persona_scores.get(slug, 0) + 2

    # Also match on question category
    category = question.category.lower()
    category_persona_map = {
        "test_prep": ["vikram-patel"],
        "study_abroad": ["amit-jalan", "priya-sharma"],
        "visa": ["mohita-gupta"],
        "language": ["vikram-patel"],
        "education_loan": ["madhav-gupta"],
    }
    for slug in category_persona_map.get(category, []):
        persona_scores[slug] = persona_scores.get(slug, 0) + 1

    if not persona_scores:
        # Default to founder for unmatched questions
        persona_scores["amit-jalan"] = 1

    # Get the top persona slug
    best_slug = max(persona_scores, key=persona_scores.get)

    # Fetch from DB
    persona = db.query(Persona).filter(Persona.slug == best_slug, Persona.is_active == True).first()

    if not persona:
        # Fallback: any active persona
        persona = db.query(Persona).filter(Persona.is_active == True).first()

    return persona
