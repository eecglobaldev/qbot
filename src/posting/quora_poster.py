"""Post answers to Quora using Playwright browser automation.

Handles login, navigation to question pages, and answer submission
with human-like behavior patterns.
"""

import logging
import random
from datetime import datetime, timezone
from pathlib import Path

from playwright.async_api import BrowserContext, Page

from src.database import ActivityLog, Answer, QuoraAccount, QuestionStatus
from src.posting.browser import human_like_delay, human_like_type

logger = logging.getLogger(__name__)

# Screenshots directory for debugging
SCREENSHOTS_DIR = Path("screenshots")
SCREENSHOTS_DIR.mkdir(exist_ok=True)


async def login_to_quora(page: Page, email: str, password: str) -> bool:
    """Log in to Quora with the given credentials.

    Returns True if login was successful, False otherwise.
    """
    try:
        await page.goto("https://www.quora.com/", wait_until="domcontentloaded", timeout=30000)
        await human_like_delay(page, 2000, 4000)

        # Check if already logged in
        profile_icon = await page.query_selector('[class*="avatar"], [aria-label="Profile"]')
        if profile_icon:
            logger.info(f"Already logged in as {email}")
            return True

        # Look for email login option
        email_field = await page.query_selector('input[name="email"], input[type="email"]')
        if not email_field:
            # Try clicking "Login" or "Email" button first
            login_btn = await page.query_selector('text="Login"')
            if login_btn:
                await login_btn.click()
                await human_like_delay(page, 1000, 2000)

            email_btn = await page.query_selector('text="Login with email"')
            if email_btn:
                await email_btn.click()
                await human_like_delay(page, 1000, 2000)

        # Type credentials
        await human_like_type(page, 'input[name="email"], input[type="email"]', email)
        await human_like_delay(page, 500, 1000)

        password_field = await page.query_selector('input[name="password"], input[type="password"]')
        if password_field:
            await human_like_type(page, 'input[name="password"], input[type="password"]', password)
            await human_like_delay(page, 500, 1000)

        # Submit
        submit_btn = await page.query_selector('button[type="submit"], button:has-text("Login")')
        if submit_btn:
            await submit_btn.click()
            await human_like_delay(page, 3000, 5000)

        # Verify login success
        await page.wait_for_load_state("networkidle", timeout=15000)
        profile_icon = await page.query_selector('[class*="avatar"], [aria-label="Profile"]')
        if profile_icon:
            logger.info(f"Successfully logged in as {email}")
            return True

        # Check for CAPTCHA
        captcha = await page.query_selector('[class*="captcha"], iframe[src*="captcha"]')
        if captcha:
            logger.warning(f"CAPTCHA detected during login for {email}")
            await page.screenshot(path=str(SCREENSHOTS_DIR / f"captcha_{email}.png"))
            return False

        logger.warning(f"Login may have failed for {email} — could not verify")
        await page.screenshot(path=str(SCREENSHOTS_DIR / f"login_fail_{email}.png"))
        return False

    except Exception as e:
        logger.error(f"Login error for {email}: {e}")
        await page.screenshot(path=str(SCREENSHOTS_DIR / f"login_error_{email}.png"))
        return False


async def post_answer(page: Page, question_url: str, answer_text: str) -> bool:
    """Navigate to a Quora question and post an answer.

    Args:
        page: Logged-in Playwright page
        question_url: Full URL of the Quora question
        answer_text: The answer text to post

    Returns:
        True if the answer was posted successfully
    """
    try:
        # Navigate to the question
        await page.goto(question_url, wait_until="domcontentloaded", timeout=30000)
        await human_like_delay(page, 2000, 4000)

        # Simulate reading the question (scroll down slowly)
        for _ in range(random.randint(2, 4)):
            await page.evaluate(f"window.scrollBy(0, {random.randint(100, 300)})")
            await human_like_delay(page, 500, 1500)

        # Look for the "Answer" button or answer input area
        answer_btn = await page.query_selector(
            'button:has-text("Answer"), [class*="AnswerButton"], [aria-label*="Answer"]'
        )
        if answer_btn:
            await answer_btn.click()
            await human_like_delay(page, 1500, 3000)

        # Find the answer editor
        editor = await page.query_selector(
            '[contenteditable="true"], [class*="editor"], [class*="AnswerEditor"], textarea'
        )
        if not editor:
            logger.error(f"Could not find answer editor on {question_url}")
            await page.screenshot(path=str(SCREENSHOTS_DIR / "no_editor.png"))
            return False

        # Click into the editor
        await editor.click()
        await human_like_delay(page, 500, 1000)

        # Type the answer with human-like speed
        # Break into paragraphs and type each with pauses
        paragraphs = answer_text.split("\n\n")
        for i, paragraph in enumerate(paragraphs):
            # Type each paragraph
            for line in paragraph.split("\n"):
                await page.keyboard.type(line, delay=random.randint(20, 60))
                if "\n" in paragraph and line != paragraph.split("\n")[-1]:
                    await page.keyboard.press("Shift+Enter")
                    await human_like_delay(page, 100, 300)

            # Add paragraph break between paragraphs
            if i < len(paragraphs) - 1:
                await page.keyboard.press("Enter")
                await page.keyboard.press("Enter")
                await human_like_delay(page, 300, 800)

            # Occasional longer pause (simulating re-reading)
            if random.random() < 0.2:
                await human_like_delay(page, 1000, 3000)

        # Review pause before submitting (human would re-read)
        await human_like_delay(page, 2000, 5000)

        # Click submit/post button
        submit_btn = await page.query_selector(
            'button:has-text("Post"), button:has-text("Submit"), button[class*="submit"]'
        )
        if submit_btn:
            await submit_btn.click()
            await human_like_delay(page, 3000, 5000)

            # Verify post success
            await page.wait_for_load_state("networkidle", timeout=15000)

            # Check for error messages
            error = await page.query_selector('[class*="error"], [class*="Error"]')
            if error:
                error_text = await error.inner_text()
                logger.error(f"Post error: {error_text}")
                return False

            logger.info(f"Successfully posted answer to {question_url}")
            return True
        else:
            logger.error("Could not find submit button")
            await page.screenshot(path=str(SCREENSHOTS_DIR / "no_submit.png"))
            return False

    except Exception as e:
        logger.error(f"Error posting answer to {question_url}: {e}")
        await page.screenshot(path=str(SCREENSHOTS_DIR / "post_error.png"))
        return False


async def save_browser_state(context: BrowserContext, profile_path: str):
    """Save the browser state (cookies, localStorage) for session persistence."""
    try:
        state = await context.storage_state()
        state_path = Path(profile_path) / "state.json"
        state_path.parent.mkdir(parents=True, exist_ok=True)
        import json

        with open(state_path, "w") as f:
            json.dump(state, f)
        logger.info(f"Browser state saved to {state_path}")
    except Exception as e:
        logger.error(f"Failed to save browser state: {e}")
