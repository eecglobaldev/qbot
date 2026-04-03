"""Tests for question scoring and filtering."""

from src.discovery.scorer import filter_questions, score_question


def test_score_ielts_question():
    score = score_question("How to prepare for IELTS in 30 days?", "test_prep")
    assert score >= 0.3, f"Expected >= 0.3, got {score}"


def test_score_study_abroad_question():
    score = score_question("What is the best country to study MBA abroad?", "study_abroad")
    assert score >= 0.3, f"Expected >= 0.3, got {score}"


def test_score_visa_question():
    score = score_question("How to apply for a student visa to Canada?", "visa")
    assert score >= 0.3, f"Expected >= 0.3, got {score}"


def test_score_irrelevant_question():
    score = score_question("What is the best cryptocurrency to invest in?", "general")
    assert score < 0.2, f"Expected < 0.2, got {score}"


def test_score_negative_keywords():
    score = score_question("How to get more upvotes on Quora partner program?", "general")
    assert score < 0.2, f"Expected < 0.2, got {score}"


def test_score_unanswered_bonus():
    score_no_answers = score_question("IELTS preparation tips", "test_prep", answer_count=0)
    score_many_answers = score_question("IELTS preparation tips", "test_prep", answer_count=50)
    assert score_no_answers > score_many_answers


def test_filter_questions():
    questions = [
        {"title": "How to prepare for IELTS?", "category": "test_prep"},
        {"title": "Best crypto to buy?", "category": "general"},
        {"title": "Study abroad in Canada for MBA", "category": "study_abroad"},
    ]
    filtered = filter_questions(questions, min_score=0.2)
    assert len(filtered) >= 2
    # Should be sorted by score descending
    for i in range(len(filtered) - 1):
        assert filtered[i]["relevance_score"] >= filtered[i + 1]["relevance_score"]


def test_filter_max_results():
    questions = [
        {"title": f"IELTS tip #{i}", "category": "test_prep"}
        for i in range(20)
    ]
    filtered = filter_questions(questions, min_score=0.0, max_results=5)
    assert len(filtered) <= 5
