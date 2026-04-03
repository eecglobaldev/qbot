"""Seed the database with EEC expert personas."""

from sqlalchemy.orm import Session

from src.database import Persona
from src.personas.definitions import PERSONAS


def seed_personas(db: Session) -> list[Persona]:
    """Insert or update persona records in the database."""
    results = []

    for p in PERSONAS:
        existing = db.query(Persona).filter(Persona.slug == p["slug"]).first()

        if existing:
            existing.name = p["name"]
            existing.title = p["title"]
            existing.bio = p["bio"]
            existing.expertise_areas = ",".join(p["expertise_areas"])
            existing.writing_style = p["writing_style"]
            results.append(existing)
        else:
            persona = Persona(
                name=p["name"],
                slug=p["slug"],
                title=p["title"],
                bio=p["bio"],
                expertise_areas=",".join(p["expertise_areas"]),
                writing_style=p["writing_style"],
            )
            db.add(persona)
            results.append(persona)

    db.commit()
    return results
