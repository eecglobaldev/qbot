"""Tests for persona matching logic — using real EEC team members."""

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


def test_ielts_matches_vikram_patel():
    """IELTS questions should match Vikram Patel (Test Prep Head, Band 9)."""
    q = _make_question("How to improve my IELTS writing score?", "test_prep")
    db = MagicMock()
    vikram = _make_persona("vikram-patel", "Vikram Patel")
    db.query.return_value.filter.return_value.first.return_value = vikram
    result = match_persona_to_question(q, db)
    assert result is not None


def test_gre_matches_vikram_patel():
    """GRE questions should match Vikram Patel."""
    q = _make_question("Best GRE study plan for 3 months?", "test_prep")
    db = MagicMock()
    vikram = _make_persona("vikram-patel", "Vikram Patel")
    db.query.return_value.filter.return_value.first.return_value = vikram
    result = match_persona_to_question(q, db)
    assert result is not None


def test_visa_matches_mohita_gupta():
    """Visa questions should match Mohita Gupta (VP Visa Strategy)."""
    q = _make_question("How to apply for student visa to Canada?", "visa")
    db = MagicMock()
    mohita = _make_persona("mohita-gupta", "Mohita Gupta")
    db.query.return_value.filter.return_value.first.return_value = mohita
    result = match_persona_to_question(q, db)
    assert result is not None


def test_education_loan_matches_madhav_gupta():
    """Education loan questions should match CA Madhav Gupta."""
    q = _make_question("How to get education loan for studying abroad?", "education_loan")
    db = MagicMock()
    madhav = _make_persona("madhav-gupta", "CA Madhav Gupta")
    db.query.return_value.filter.return_value.first.return_value = madhav
    result = match_persona_to_question(q, db)
    assert result is not None


def test_australia_matches_anita_or_anirudh():
    """Australia questions should match Anita Desai or Anirudh Gupta."""
    q = _make_question("How to study in Australia and get PR?", "study_abroad")
    db = MagicMock()
    anita = _make_persona("anita-desai", "Anita Desai")
    db.query.return_value.filter.return_value.first.return_value = anita
    result = match_persona_to_question(q, db)
    assert result is not None


def test_germany_matches_rahul_mehta():
    """Germany/Europe questions should match Rahul Mehta."""
    q = _make_question("Can I study in Germany for free?", "study_abroad")
    db = MagicMock()
    rahul = _make_persona("rahul-mehta", "Rahul Mehta")
    db.query.return_value.filter.return_value.first.return_value = rahul
    result = match_persona_to_question(q, db)
    assert result is not None


def test_usa_matches_priya_sharma():
    """USA study questions should match Priya Sharma."""
    q = _make_question("How to get F-1 visa for studying in USA?", "study_abroad")
    db = MagicMock()
    priya = _make_persona("priya-sharma", "Priya Sharma")
    db.query.return_value.filter.return_value.first.return_value = priya
    result = match_persona_to_question(q, db)
    assert result is not None


def test_topic_persona_map_completeness():
    """All persona slugs in the map should be valid real EEC team members."""
    valid_slugs = {
        "amit-jalan", "mili-mehta", "madhav-gupta", "mohita-gupta",
        "anirudh-gupta", "ridhika-jalan", "priya-sharma", "rahul-mehta",
        "anita-desai", "vikram-patel",
    }
    for keyword, slugs in TOPIC_PERSONA_MAP.items():
        for slug in slugs:
            assert slug in valid_slugs, f"Unknown persona slug '{slug}' for keyword '{keyword}'"
