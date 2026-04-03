"""FastAPI dashboard for the EEC Quora Bot.

Provides a web interface for:
- Viewing discovered questions and their status
- Reviewing and approving/rejecting generated answers
- Monitoring account health and system status
- Triggering discovery and generation runs
"""

import logging
from datetime import datetime, timezone

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.config import settings
from src.database import Answer, Persona, Question, QuestionStatus, get_db, init_db
from src.generation.generator import generate_answer, regenerate_answer
from src.monitoring.health import check_alerts, get_recent_activity, get_system_health
from src.personas.matcher import match_persona_to_question
from src.personas.seed import seed_personas

logger = logging.getLogger(__name__)

app = FastAPI(title="EEC Quora Bot Dashboard", version="0.1.0")

templates = Jinja2Templates(directory="templates")


# --- Pydantic models for API ---


class AnswerReview(BaseModel):
    action: str  # "approve", "reject", "regenerate"
    feedback: str = ""


class GenerateRequest(BaseModel):
    question_id: int
    persona_id: int | None = None


# --- Startup ---


@app.on_event("startup")
def startup():
    init_db()
    db = get_db()
    try:
        seed_personas(db)
        logger.info("Database initialized, personas seeded")
    finally:
        db.close()


# --- Dashboard Pages ---


@app.get("/", response_class=HTMLResponse)
async def dashboard_home(request: Request):
    db = get_db()
    try:
        health = get_system_health(db)
        alerts = check_alerts(db)
        activity = get_recent_activity(db, limit=20)
        return templates.TemplateResponse("dashboard.html", {
            "request": request,
            "health": health,
            "alerts": alerts,
            "activity": activity,
        })
    finally:
        db.close()


# --- API: Questions ---


@app.get("/api/questions")
async def list_questions(status: str | None = None, limit: int = 50, offset: int = 0):
    db = get_db()
    try:
        query = db.query(Question).order_by(Question.relevance_score.desc())
        if status:
            query = query.filter(Question.status == status)
        questions = query.offset(offset).limit(limit).all()
        total = query.count()

        return {
            "questions": [
                {
                    "id": q.id,
                    "url": q.url,
                    "title": q.title,
                    "category": q.category,
                    "status": q.status,
                    "relevance_score": q.relevance_score,
                    "answer_count": q.answer_count,
                    "discovered_at": q.discovered_at.isoformat() if q.discovered_at else None,
                }
                for q in questions
            ],
            "total": total,
        }
    finally:
        db.close()


@app.post("/api/questions/{question_id}/generate")
async def generate_answer_for_question(question_id: int, req: GenerateRequest | None = None):
    """Generate an answer for a specific question."""
    db = get_db()
    try:
        question = db.query(Question).filter(Question.id == question_id).first()
        if not question:
            raise HTTPException(404, "Question not found")

        # Select persona
        if req and req.persona_id:
            persona = db.query(Persona).filter(Persona.id == req.persona_id).first()
        else:
            persona = match_persona_to_question(question, db)

        if not persona:
            raise HTTPException(400, "No suitable persona found")

        # Generate answer
        answer = generate_answer(question, persona)
        db.add(answer)
        question.status = QuestionStatus.REVIEW
        db.commit()
        db.refresh(answer)

        return {
            "answer_id": answer.id,
            "persona": persona.name,
            "content": answer.content,
            "word_count": answer.word_count,
            "status": answer.status,
        }
    finally:
        db.close()


# --- API: Answers / Review Queue ---


@app.get("/api/answers")
async def list_answers(status: str | None = None, limit: int = 50):
    db = get_db()
    try:
        query = db.query(Answer).order_by(Answer.created_at.desc())
        if status:
            query = query.filter(Answer.status == status)
        answers = query.limit(limit).all()

        return {
            "answers": [
                {
                    "id": a.id,
                    "question_id": a.question_id,
                    "question_title": a.question.title if a.question else "",
                    "question_url": a.question.url if a.question else "",
                    "persona_name": a.persona.name if a.persona else "",
                    "content": a.content,
                    "word_count": a.word_count,
                    "status": a.status,
                    "reviewer_notes": a.reviewer_notes,
                    "created_at": a.created_at.isoformat() if a.created_at else None,
                    "posted_at": a.posted_at.isoformat() if a.posted_at else None,
                }
                for a in answers
            ]
        }
    finally:
        db.close()


@app.post("/api/answers/{answer_id}/review")
async def review_answer(answer_id: int, review: AnswerReview):
    """Approve, reject, or request regeneration of an answer."""
    db = get_db()
    try:
        answer = db.query(Answer).filter(Answer.id == answer_id).first()
        if not answer:
            raise HTTPException(404, "Answer not found")

        if review.action == "approve":
            answer.status = "approved"
            answer.reviewer_notes = review.feedback
            question = db.query(Question).filter(Question.id == answer.question_id).first()
            if question:
                question.status = QuestionStatus.APPROVED

        elif review.action == "reject":
            answer.status = "rejected"
            answer.reviewer_notes = review.feedback
            question = db.query(Question).filter(Question.id == answer.question_id).first()
            if question:
                question.status = QuestionStatus.REJECTED

        elif review.action == "regenerate":
            persona = db.query(Persona).filter(Persona.id == answer.persona_id).first()
            question = db.query(Question).filter(Question.id == answer.question_id).first()

            if persona and question:
                new_content = regenerate_answer(answer, review.feedback, persona, question)
                answer.content = new_content
                answer.word_count = len(new_content.split())
                answer.reviewer_notes = f"Regenerated with feedback: {review.feedback}"
                answer.updated_at = datetime.now(timezone.utc)
        else:
            raise HTTPException(400, f"Invalid action: {review.action}")

        db.commit()
        return {"status": "ok", "answer_status": answer.status}
    finally:
        db.close()


# --- API: Personas ---


@app.get("/api/personas")
async def list_personas():
    db = get_db()
    try:
        personas = db.query(Persona).filter(Persona.is_active == True).all()
        return {
            "personas": [
                {
                    "id": p.id,
                    "name": p.name,
                    "slug": p.slug,
                    "title": p.title,
                    "expertise_areas": p.expertise_areas.split(","),
                    "daily_post_count": p.daily_post_count,
                    "is_active": p.is_active,
                }
                for p in personas
            ]
        }
    finally:
        db.close()


# --- API: Health & Monitoring ---


@app.get("/api/health")
async def health_check():
    db = get_db()
    try:
        return get_system_health(db)
    finally:
        db.close()


@app.get("/api/alerts")
async def get_alerts():
    db = get_db()
    try:
        return {"alerts": check_alerts(db)}
    finally:
        db.close()


@app.get("/api/activity")
async def get_activity(limit: int = 50):
    db = get_db()
    try:
        return {"activity": get_recent_activity(db, limit)}
    finally:
        db.close()
