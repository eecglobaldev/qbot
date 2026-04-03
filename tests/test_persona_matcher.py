"""Tests for persona matching logic."""

from unittest.mock import MagicMock

from src.personas.matcher import TOPIC_PERSONA_MAP, match_persona_to_question


def _make_question(title: str, category: str = "test_prep", topics: str = ""):
    q = MagicMock()
    q.title = title
    q.category = category
    q.topics = topics
    return q


def _make_persona(slug: str, name: str = "Test"):
    p = MagicMock()
    p.slug = slug
    p.name = name
    p.is_active = True
    return p


def test_ielts_matches_priya():
    """IELTS questions should match Priya Sharma."""
    q = _make_question("How to improve my IELTS writing score?", "test_prep")

    db = MagicMock()
    priya = _make_persona("priya-sharma", "Dr. Priya Sharma")
    db.query.return_value.filter.return_value.first.return_value = priya

    result = match_persona_to_question(q, db)
    assert result is not None


def test_gre_matches_rahul():
    """GRE questions should match Rahul Kapoor."""
    q = _make_question("Best GRE study plan for 3 months?", "test_prep")

    db = MagicMock()
    rahul = _make_persona("rahul-kapoor", "Rahul Kapoor")
    db.query.return_value.filter.return_value.first.return_value = rahul

    result = match_persona_to_question(q, db)
    assert result is not None


def test_visa_matches_vikram():
    """Visa questions should match Vikram Desai."""
    q = _make_question("How to apply for student visa to Canada?", "visa")

    db = MagicMock()
    vikram = _make_persona("vikram-desai", "Vikram Desai")
    db.query.return_value.filter.return_value.first.return_value = vikram

    result = match_persona_to_question(q, db)
    assert result is not None


def test_topic_persona_map_completeness():
    """All persona slugs in the map should be valid."""
    valid_slugs = {
        "amit-jalan", "priya-sharma", "rahul-kapoor", "sneha-patel",
        "meera-iyer", "vikram-desai", "ananya-krishnan", "nikhil-mehta",
    }
    for keyword, slugs in TOPIC_PERSONA_MAP.items():
        for slug in slugs:
            assert slug in valid_slugs, f"Unknown persona slug '{slug}' for keyword '{keyword}'"
