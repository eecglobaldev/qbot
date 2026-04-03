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
from src.database import Answer, Persona, Question, QuestionStatus, QuoraAccount, AccountHealth, get_db, init_db
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


class PersonaUpdate(BaseModel):
    name: str | None = None
    title: str | None = None
    bio: str | None = None
    expertise_areas: str | None = None
    writing_style: str | None = None
    is_active: bool | None = None


class AccountCreate(BaseModel):
    persona_id: int
    email: str
    password_ref: str = ""  # reference key to retrieve password from secrets manager
    browser_profile_path: str = ""
    proxy_url: str = ""
    notes: str = ""


class AccountUpdate(BaseModel):
    email: str | None = None
    password_ref: str | None = None
    health: str | None = None
    browser_profile_path: str | None = None
    proxy_url: str | None = None
    notes: str | None = None


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
async def list_personas(include_inactive: bool = False):
    db = get_db()
    try:
        query = db.query(Persona)
        if not include_inactive:
            query = query.filter(Persona.is_active == True)
        personas = query.all()
        return {
            "personas": [
                {
                    "id": p.id,
                    "name": p.name,
                    "slug": p.slug,
                    "title": p.title,
                    "bio": p.bio,
                    "expertise_areas": p.expertise_areas.split(","),
                    "writing_style": p.writing_style,
                    "daily_post_count": p.daily_post_count,
                    "is_active": p.is_active,
                    "accounts": [
                        {
                            "id": a.id,
                            "email": a.email,
                            "health": a.health,
                            "posts_today": a.posts_today,
                            "total_posts": a.total_posts,
                            "last_active": a.last_active.isoformat() if a.last_active else None,
                            "browser_profile_path": a.browser_profile_path,
                            "proxy_url": a.proxy_url,
                            "notes": a.notes,
                        }
                        for a in p.accounts
                    ],
                }
                for p in personas
            ]
        }
    finally:
        db.close()


@app.get("/api/personas/{persona_id}")
async def get_persona(persona_id: int):
    db = get_db()
    try:
        persona = db.query(Persona).filter(Persona.id == persona_id).first()
        if not persona:
            raise HTTPException(404, "Persona not found")
        return {
            "id": persona.id,
            "name": persona.name,
            "slug": persona.slug,
            "title": persona.title,
            "bio": persona.bio,
            "expertise_areas": persona.expertise_areas,
            "writing_style": persona.writing_style,
            "is_active": persona.is_active,
            "daily_post_count": persona.daily_post_count,
            "last_post_date": persona.last_post_date,
            "accounts": [
                {
                    "id": a.id,
                    "email": a.email,
                    "health": a.health,
                    "posts_today": a.posts_today,
                    "total_posts": a.total_posts,
                    "last_active": a.last_active.isoformat() if a.last_active else None,
                    "browser_profile_path": a.browser_profile_path,
                    "proxy_url": a.proxy_url,
                    "notes": a.notes,
                }
                for a in persona.accounts
            ],
        }
    finally:
        db.close()


@app.put("/api/personas/{persona_id}")
async def update_persona(persona_id: int, update: PersonaUpdate):
    """Update persona details (name, title, bio, expertise, writing style, active status)."""
    db = get_db()
    try:
        persona = db.query(Persona).filter(Persona.id == persona_id).first()
        if not persona:
            raise HTTPException(404, "Persona not found")

        if update.name is not None:
            persona.name = update.name
        if update.title is not None:
            persona.title = update.title
        if update.bio is not None:
            persona.bio = update.bio
        if update.expertise_areas is not None:
            persona.expertise_areas = update.expertise_areas
        if update.writing_style is not None:
            persona.writing_style = update.writing_style
        if update.is_active is not None:
            persona.is_active = update.is_active

        db.commit()
        return {"status": "ok", "persona_id": persona.id, "name": persona.name}
    finally:
        db.close()


# --- API: Quora Accounts ---


@app.get("/api/accounts")
async def list_accounts():
    db = get_db()
    try:
        accounts = db.query(QuoraAccount).all()
        return {
            "accounts": [
                {
                    "id": a.id,
                    "persona_id": a.persona_id,
                    "persona_name": a.persona.name if a.persona else "",
                    "email": a.email,
                    "health": a.health,
                    "posts_today": a.posts_today,
                    "total_posts": a.total_posts,
                    "last_active": a.last_active.isoformat() if a.last_active else None,
                    "browser_profile_path": a.browser_profile_path,
                    "proxy_url": a.proxy_url,
                    "notes": a.notes,
                }
                for a in accounts
            ]
        }
    finally:
        db.close()


@app.post("/api/accounts")
async def create_account(account: AccountCreate):
    """Add a new Quora account linked to a persona."""
    db = get_db()
    try:
        persona = db.query(Persona).filter(Persona.id == account.persona_id).first()
        if not persona:
            raise HTTPException(404, "Persona not found")

        # Check for duplicate email
        existing = db.query(QuoraAccount).filter(QuoraAccount.email == account.email).first()
        if existing:
            raise HTTPException(400, f"Account with email {account.email} already exists")

        new_account = QuoraAccount(
            persona_id=account.persona_id,
            email=account.email,
            health=AccountHealth.HEALTHY,
            browser_profile_path=account.browser_profile_path or f"browser_data/{persona.slug}",
            proxy_url=account.proxy_url,
            notes=account.notes,
        )
        db.add(new_account)

        # Also update the persona's quora_email if not set
        if not persona.quora_email:
            persona.quora_email = account.email
        if account.password_ref:
            persona.quora_password_ref = account.password_ref

        db.commit()
        db.refresh(new_account)
        return {
            "status": "ok",
            "account_id": new_account.id,
            "email": new_account.email,
            "persona": persona.name,
        }
    finally:
        db.close()


@app.put("/api/accounts/{account_id}")
async def update_account(account_id: int, update: AccountUpdate):
    """Update Quora account details (email, credentials ref, health, proxy, etc.)."""
    db = get_db()
    try:
        account = db.query(QuoraAccount).filter(QuoraAccount.id == account_id).first()
        if not account:
            raise HTTPException(404, "Account not found")

        if update.email is not None:
            account.email = update.email
        if update.password_ref is not None:
            # Update the persona's password reference too
            persona = db.query(Persona).filter(Persona.id == account.persona_id).first()
            if persona:
                persona.quora_password_ref = update.password_ref
        if update.health is not None:
            if update.health not in [h.value for h in AccountHealth]:
                raise HTTPException(400, f"Invalid health status. Must be one of: {[h.value for h in AccountHealth]}")
            account.health = update.health
        if update.browser_profile_path is not None:
            account.browser_profile_path = update.browser_profile_path
        if update.proxy_url is not None:
            account.proxy_url = update.proxy_url
        if update.notes is not None:
            account.notes = update.notes

        db.commit()
        return {"status": "ok", "account_id": account.id}
    finally:
        db.close()


@app.delete("/api/accounts/{account_id}")
async def delete_account(account_id: int):
    """Remove a Quora account."""
    db = get_db()
    try:
        account = db.query(QuoraAccount).filter(QuoraAccount.id == account_id).first()
        if not account:
            raise HTTPException(404, "Account not found")
        db.delete(account)
        db.commit()
        return {"status": "ok", "deleted_account_id": account_id}
    finally:
        db.close()


@app.post("/api/accounts/{account_id}/reset-health")
async def reset_account_health(account_id: int):
    """Reset an account's health status back to healthy."""
    db = get_db()
    try:
        account = db.query(QuoraAccount).filter(QuoraAccount.id == account_id).first()
        if not account:
            raise HTTPException(404, "Account not found")
        account.health = AccountHealth.HEALTHY
        account.posts_today = 0
        db.commit()
        return {"status": "ok", "account_id": account.id, "health": account.health}
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
