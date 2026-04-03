"""Generate answers using Google Gemini API with persona-appropriate voice."""

import logging
from datetime import datetime, timezone

from google import genai

from src.config import settings
from src.database import Answer, Persona, Question

logger = logging.getLogger(__name__)


def _count_words(text: str) -> int:
    return len(text.split())


def _get_client() -> genai.Client:
    """Create a Gemini API client."""
    return genai.Client(api_key=settings.gemini_api_key)


def generate_answer(question: Question, persona: Persona) -> Answer:
    """Generate an answer for a question using the specified persona.

    Uses Google Gemini API to generate a high-quality, persona-appropriate answer.
    Returns an Answer object (not yet committed to DB).
    """
    from src.generation.prompt_builder import build_answer_prompt

    prompt = build_answer_prompt(question, persona)
    client = _get_client()

    logger.info(f"Generating answer for Q#{question.id} '{question.title[:60]}...' as {persona.name}")

    response = client.models.generate_content(
        model=settings.gemini_model,
        contents=prompt,
    )

    content = response.text.strip()
    word_count = _count_words(content)

    # Validate answer quality
    if word_count < settings.answer_min_words:
        logger.warning(f"Answer too short ({word_count} words), regenerating...")
        retry_prompt = (
            prompt
            + f"\n\nIMPORTANT: Your previous answer was only {word_count} words. "
            f"Please write at least {settings.answer_min_words} words while maintaining quality."
        )
        response = client.models.generate_content(
            model=settings.gemini_model,
            contents=retry_prompt,
        )
        content = response.text.strip()
        word_count = _count_words(content)

    answer = Answer(
        question_id=question.id,
        persona_id=persona.id,
        content=content,
        word_count=word_count,
        status="draft",
        created_at=datetime.now(timezone.utc),
    )

    logger.info(f"Generated {word_count}-word answer for Q#{question.id} as {persona.name}")
    return answer


def regenerate_answer(answer: Answer, feedback: str, persona: Persona, question: Question) -> str:
    """Regenerate an answer incorporating reviewer feedback.

    Used when a human reviewer wants changes to a draft answer.
    """
    from src.generation.prompt_builder import build_answer_prompt

    base_prompt = build_answer_prompt(question, persona)

    revision_prompt = f"""{base_prompt}

---

**REVISION REQUEST**

The previous draft was:
{answer.content}

The reviewer provided this feedback:
{feedback}

Please rewrite the answer incorporating this feedback while maintaining the persona's voice and all other guidelines.
Write ONLY the revised answer text.
"""

    client = _get_client()

    response = client.models.generate_content(
        model=settings.gemini_model,
        contents=revision_prompt,
    )

    return response.text.strip()
