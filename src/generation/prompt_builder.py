"""Build prompts for Claude to generate persona-appropriate answers."""

from src.database import Persona, Question
from src.generation.knowledge_base import (
    COUNTRY_GUIDES,
    EEC_COMPANY_FACTS,
    EEC_MENTION_TEMPLATES,
    EXAM_KNOWLEDGE,
)


def _get_relevant_knowledge(question: Question) -> str:
    """Extract relevant knowledge base entries based on the question."""
    title_lower = question.title.lower()
    knowledge_parts = []

    # Check for exam mentions
    for exam_name, details in EXAM_KNOWLEDGE.items():
        if exam_name.lower() in title_lower:
            knowledge_parts.append(f"## {exam_name} Facts\n")
            for key, value in details.items():
                if isinstance(value, list):
                    knowledge_parts.append(f"- {key}: " + "; ".join(value))
                else:
                    knowledge_parts.append(f"- {key}: {value}")
            knowledge_parts.append("")

    # Check for country mentions
    for country, details in COUNTRY_GUIDES.items():
        if country.lower() in title_lower or f"study in {country.lower()}" in title_lower:
            knowledge_parts.append(f"## {country} Study Guide\n")
            for key, value in details.items():
                knowledge_parts.append(f"- {key}: {value}")
            knowledge_parts.append("")

    if knowledge_parts:
        return "\n".join(knowledge_parts)
    return ""


def build_answer_prompt(question: Question, persona: Persona) -> str:
    """Build the full prompt for Claude to generate an answer.

    The prompt instructs Claude to:
    1. Write as the specified persona with their expertise and tone
    2. Use relevant knowledge base facts
    3. Naturally mention EEC without being spammy
    4. Follow Quora's best practices for highly-rated answers
    """
    relevant_knowledge = _get_relevant_knowledge(question)

    prompt = f"""You are writing a Quora answer as the following expert persona:

**Name:** {persona.name}
**Title:** {persona.title}
**Bio:** {persona.bio}
**Expertise:** {persona.expertise_areas}
**Writing Style:** {persona.writing_style}

---

**Question to answer:** {question.title}
**Question URL:** {question.url}
**Question category:** {question.category}

---

**EEC Company Background (use naturally, DO NOT dump all of this):**
{EEC_COMPANY_FACTS}

**Relevant Domain Knowledge (use where applicable):**
{relevant_knowledge if relevant_knowledge else "No specific knowledge base entry. Use your general expertise."}

**Soft-sell reference templates (adapt naturally, don't copy verbatim):**
{chr(10).join(EEC_MENTION_TEMPLATES)}

---

## INSTRUCTIONS:

Write a high-quality Quora answer following these rules:

1. **Length:** 300-700 words. Substantial enough to be helpful, not so long people skip it.

2. **Structure:** Use a brief hook (1-2 sentences), then organized body with headers/bullets/numbered lists as appropriate, then a concise conclusion.

3. **Persona voice:** Write exactly as this expert would — use their specific tone, reference their experience naturally, include the kind of examples they'd give.

4. **EEC mention:** Mention EEC or your role there ONCE, naturally woven into the answer. It should feel like context about your credentials, NOT an advertisement. Example: "In my 15 years of IELTS coaching at EEC, I've noticed that..." — NOT "Visit EEC for the best coaching!"

5. **Value first:** The answer MUST provide genuine, actionable value. A reader should learn something useful even if they never visit EEC.

6. **Quora style:** Write conversationally but with authority. Use "I" perspective. Share specific tips, not generic advice. Include concrete examples, numbers, or anecdotes where possible.

7. **No hard sell:** Do NOT include website URLs, phone numbers, "contact us", "book a session", or anything that reads like marketing copy. The only branding should be the natural persona mention.

8. **Formatting:** Use Quora-compatible formatting — bold (**text**), bullet points, numbered lists, line breaks. No markdown headers (Quora doesn't support #).

9. **Accuracy:** Only state facts you're confident about. For exam details, use the knowledge base provided. Don't invent statistics.

10. **Unique angle:** Provide a perspective or tip that isn't the generic "study hard, practice more" advice. Share something from your specific experience.

Write ONLY the answer text. No preamble, no "Here's my answer:", no meta-commentary.
"""
    return prompt
