"""Match discovered questions to the best expert persona."""

import re

from sqlalchemy.orm import Session

from src.database import Persona, Question


# Keyword-to-persona mapping for fast matching
TOPIC_PERSONA_MAP: dict[str, list[str]] = {
    # Test Prep - IELTS & PTE
    "ielts": ["priya-sharma"],
    "pte": ["priya-sharma"],
    "pte academic": ["priya-sharma"],
    "pte core": ["priya-sharma"],
    "band score": ["priya-sharma"],
    "english proficiency": ["priya-sharma", "ananya-krishnan"],

    # Test Prep - GRE & SAT
    "gre": ["rahul-kapoor"],
    "sat": ["rahul-kapoor"],
    "d-sat": ["rahul-kapoor"],
    "gmat": ["rahul-kapoor"],
    "quantitative": ["rahul-kapoor"],
    "analytical writing": ["rahul-kapoor"],

    # Test Prep - TOEFL, Duolingo, Others
    "toefl": ["ananya-krishnan"],
    "duolingo": ["ananya-krishnan"],
    "celpip": ["ananya-krishnan"],
    "languagecert": ["ananya-krishnan"],
    "oet": ["ananya-krishnan"],

    # Study Abroad
    "study abroad": ["sneha-patel", "amit-jalan"],
    "study in canada": ["sneha-patel"],
    "study in uk": ["sneha-patel"],
    "study in australia": ["sneha-patel"],
    "study in ireland": ["sneha-patel"],
    "study in usa": ["amit-jalan", "sneha-patel"],
    "study in germany": ["meera-iyer", "sneha-patel"],
    "mba abroad": ["amit-jalan"],
    "ms abroad": ["amit-jalan", "sneha-patel"],
    "mim": ["sneha-patel"],
    "masters in management": ["sneha-patel"],
    "undergraduate abroad": ["sneha-patel", "rahul-kapoor"],
    "sop": ["sneha-patel"],
    "statement of purpose": ["sneha-patel"],
    "lor": ["sneha-patel"],
    "university admission": ["sneha-patel", "amit-jalan"],
    "scholarship": ["sneha-patel", "nikhil-mehta"],

    # MBBS
    "mbbs": ["meera-iyer"],
    "medical": ["meera-iyer"],
    "neet": ["meera-iyer"],
    "nmc": ["meera-iyer"],

    # Visa
    "visa": ["vikram-desai"],
    "student visa": ["vikram-desai"],
    "spouse visa": ["vikram-desai"],
    "tourist visa": ["vikram-desai"],
    "visa extension": ["vikram-desai"],
    "visa interview": ["vikram-desai"],
    "immigration": ["vikram-desai"],
    "visa rejection": ["vikram-desai"],

    # Education Loan & Finance
    "education loan": ["nikhil-mehta"],
    "student loan": ["nikhil-mehta"],
    "loan": ["nikhil-mehta"],
    "financial": ["nikhil-mehta"],
    "cost of studying": ["nikhil-mehta"],
    "tuition fee": ["nikhil-mehta"],
    "forex": ["nikhil-mehta"],

    # Language
    "spoken english": ["priya-sharma", "ananya-krishnan"],
    "french": ["ananya-krishnan"],
    "german": ["ananya-krishnan", "meera-iyer"],
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
        "test_prep": ["priya-sharma", "rahul-kapoor", "ananya-krishnan"],
        "study_abroad": ["sneha-patel", "amit-jalan"],
        "visa": ["vikram-desai"],
        "language": ["ananya-krishnan", "priya-sharma"],
        "education_loan": ["nikhil-mehta"],
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
