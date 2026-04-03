"""Orchestrate a full posting run: login, post answers, save state.

Combines browser management, account selection, and posting into
a single async workflow.
"""

import asyncio
import logging
import os

from sqlalchemy.orm import Session

from src.database import Persona, get_db
from src.posting.browser import BrowserManager
from src.posting.quora_poster import login_to_quora, post_answer, save_browser_state
from src.posting.scheduler import calculate_post_delay, get_next_posting_batch, record_post_result

logger = logging.getLogger(__name__)


def _resolve_password(persona: Persona, password_ref: str) -> str:
    """Resolve a password reference to the actual password.

    Password references are environment variable names (e.g., QUORA_PASS_PRIYA).
    This avoids storing actual passwords in the database.
    """
    if not password_ref:
        # Fall back to persona-level reference
        password_ref = persona.quora_password_ref

    if not password_ref:
        logger.error(f"No password reference for persona {persona.name}")
        return ""

    # Look up in environment variables
    password = os.environ.get(password_ref, "")
    if not password:
        logger.error(f"Password env var '{password_ref}' not set for persona {persona.name}")
    return password


async def run_posting_cycle(headless: bool = True, dry_run: bool = False):
    """Run a full posting cycle.

    Steps:
    1. Get the next batch of approved answers
    2. For each answer, login with the appropriate account
    3. Post the answer
    4. Record results
    5. Wait between posts

    Args:
        headless: Run browser in headless mode
        dry_run: If True, do everything except actually posting (for testing)
    """
    db = get_db()
    browser_mgr = BrowserManager()

    try:
        batch = get_next_posting_batch(db)
        if not batch:
            logger.info("No approved answers to post")
            return

        logger.info(f"Starting posting cycle: {len(batch)} answers queued")
        await browser_mgr.start(headless=headless)

        for i, item in enumerate(batch):
            answer = item["answer"]
            question = item["question"]
            persona = item["persona"]
            account = item["account"]

            logger.info(
                f"[{i+1}/{len(batch)}] Posting answer #{answer.id} "
                f"to '{question.title[:50]}...' as {persona.name} ({account.email})"
            )

            # Create browser context with this account's profile
            profile_path = account.browser_profile_path or f"browser_data/{persona.slug}"
            context = await browser_mgr.new_context(
                profile_path=profile_path,
                proxy_url=account.proxy_url or None,
            )
            page = await context.new_page()

            try:
                # Login
                password = _resolve_password(persona, account.notes)  # notes can hold password_ref override
                if not password:
                    password = _resolve_password(persona, "")

                logged_in = await login_to_quora(page, account.email, password)
                if not logged_in:
                    logger.warning(f"Login failed for {account.email}, skipping")
                    record_post_result(db, answer, account, question, False, "Login failed")
                    continue

                if dry_run:
                    logger.info(f"[DRY RUN] Would post answer #{answer.id} to {question.url}")
                    record_post_result(db, answer, account, question, True, "dry_run")
                    continue

                # Post the answer
                result = await post_answer(page, question.url, answer.content)
                record_post_result(
                    db, answer, account, question,
                    success=result["success"],
                    error_message=result.get("error", ""),
                )

                # Save browser state for next time
                await save_browser_state(context, profile_path)

            except Exception as e:
                logger.error(f"Posting error for answer #{answer.id}: {e}")
                record_post_result(db, answer, account, question, False, str(e))

            finally:
                await page.close()
                await context.close()

            # Wait between posts (unless it's the last one)
            if i < len(batch) - 1:
                delay = calculate_post_delay()
                logger.info(f"Waiting {delay}s before next post...")
                await asyncio.sleep(delay)

    except Exception as e:
        logger.error(f"Posting cycle error: {e}")
    finally:
        await browser_mgr.stop()
        db.close()
