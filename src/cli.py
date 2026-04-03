"""CLI entry point for the EEC Quora Bot."""

import argparse
import asyncio
import logging
import sys

import uvicorn

from src.config import settings
from src.database import get_db, init_db
from src.personas.seed import seed_personas

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper()),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def cmd_init():
    """Initialize the database and seed personas."""
    init_db()
    db = get_db()
    try:
        personas = seed_personas(db)
        print(f"Database initialized. {len(personas)} personas seeded:")
        for p in personas:
            print(f"  - {p.name} ({p.slug}): {p.title}")
    finally:
        db.close()


def cmd_discover():
    """Run the question discovery pipeline."""
    from src.discovery.pipeline import run_discovery

    init_db()
    db = get_db()
    try:
        questions = asyncio.run(run_discovery(db))
        print(f"\nDiscovered {len(questions)} new questions:")
        for q in questions[:20]:
            print(f"  [{q.category}] {q.title[:80]}...")
            print(f"    Score: {q.relevance_score:.2f} | URL: {q.url}")
    finally:
        db.close()


def cmd_generate(question_id: int | None = None):
    """Generate answers for discovered questions."""
    from src.generation.generator import generate_answer
    from src.personas.matcher import match_persona_to_question

    init_db()
    db = get_db()
    try:
        from src.database import Question, QuestionStatus

        if question_id:
            questions = [db.query(Question).filter(Question.id == question_id).first()]
            if not questions[0]:
                print(f"Question #{question_id} not found")
                return
        else:
            # Generate for all discovered questions without answers
            questions = (
                db.query(Question)
                .filter(Question.status == QuestionStatus.DISCOVERED)
                .order_by(Question.relevance_score.desc())
                .limit(10)
                .all()
            )

        if not questions:
            print("No questions to generate answers for.")
            return

        print(f"Generating answers for {len(questions)} questions...\n")

        for q in questions:
            persona = match_persona_to_question(q, db)
            if not persona:
                print(f"  No persona match for: {q.title[:60]}")
                continue

            print(f"  Q: {q.title[:70]}...")
            print(f"  Persona: {persona.name}")

            answer = generate_answer(q, persona)
            db.add(answer)
            q.status = QuestionStatus.REVIEW
            db.commit()

            print(f"  Answer: {answer.word_count} words (status: {answer.status})")
            print(f"  Preview: {answer.content[:150]}...\n")

    finally:
        db.close()


def cmd_dashboard():
    """Start the web dashboard."""
    print(f"Starting EEC Quora Bot Dashboard on http://{settings.dashboard_host}:{settings.dashboard_port}")
    uvicorn.run(
        "src.dashboard.app:app",
        host=settings.dashboard_host,
        port=settings.dashboard_port,
        reload=True,
    )


def cmd_status():
    """Show current system status."""
    from src.monitoring.health import check_alerts, get_system_health

    init_db()
    db = get_db()
    try:
        health = get_system_health(db)
        alerts = check_alerts(db)

        print("=" * 60)
        print("  EEC Quora Bot — System Status")
        print("=" * 60)

        print(f"\n  Questions:")
        for key, val in health["questions"].items():
            print(f"    {key:>15}: {val}")

        print(f"\n  Answers:")
        for key, val in health["answers"].items():
            print(f"    {key:>15}: {val}")

        print(f"\n  Accounts:")
        for key, val in health["accounts"].items():
            print(f"    {key:>15}: {val}")

        print(f"\n  Failures (24h): {health['recent_failures_24h']}")

        if alerts:
            print(f"\n  Alerts:")
            for a in alerts:
                print(f"    [{a['level'].upper()}] {a['message']}")
        else:
            print(f"\n  No active alerts.")

        print()
    finally:
        db.close()


def main():
    parser = argparse.ArgumentParser(description="EEC Quora Bot — Automated Quora Marketing Tool")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # init
    subparsers.add_parser("init", help="Initialize database and seed personas")

    # discover
    subparsers.add_parser("discover", help="Run question discovery pipeline")

    # generate
    gen_parser = subparsers.add_parser("generate", help="Generate answers for discovered questions")
    gen_parser.add_argument("--question-id", type=int, help="Generate for a specific question ID")

    # dashboard
    subparsers.add_parser("dashboard", help="Start the web dashboard")

    # status
    subparsers.add_parser("status", help="Show system status")

    args = parser.parse_args()

    if args.command == "init":
        cmd_init()
    elif args.command == "discover":
        cmd_discover()
    elif args.command == "generate":
        cmd_generate(getattr(args, "question_id", None))
    elif args.command == "dashboard":
        cmd_dashboard()
    elif args.command == "status":
        cmd_status()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
