"""Post answers to Quora using Playwright browser automation.

Uses a multi-strategy selector approach: Quora uses dynamic class names
that change on deploys, so we use multiple fallback selectors for each
element (data attributes, aria labels, text content, structural queries).

Quora's known selector patterns:
- puppeteer_test_* classes (semi-stable test identifiers)
- q-click-wrapper elements for clickable areas
- data-functional-selector attributes
- contenteditable divs for rich text editing
"""

import json
import logging
import random
from datetime import datetime, timezone
from pathlib import Path

from playwright.async_api import BrowserContext, Page, TimeoutError as PlaywrightTimeout

from src.posting.browser import human_like_delay

logger = logging.getLogger(__name__)

SCREENSHOTS_DIR = Path("screenshots")
SCREENSHOTS_DIR.mkdir(exist_ok=True)


# ---------------------------------------------------------------------------
# Selector strategies — ordered from most to least reliable per element.
# Each list is tried in order; the first match wins.
# ---------------------------------------------------------------------------

SELECTORS = {
    # --- Login page ---
    "login_email_input": [
        'input[name="email"]',
        'input[type="email"]',
        'input[placeholder*="Email"]',
        'input[placeholder*="email"]',
        'input[autocomplete="email"]',
        '#email',
    ],
    "login_password_input": [
        'input[name="password"]',
        'input[type="password"]',
        'input[placeholder*="Password"]',
        'input[placeholder*="password"]',
        'input[autocomplete="current-password"]',
    ],
    "login_submit_button": [
        'button[type="submit"]',
        'button:has-text("Login")',
        'button:has-text("Log in")',
        'button:has-text("Log In")',
        'input[type="submit"]',
        '[data-functional-selector="login-button"]',
    ],
    "login_with_email_link": [
        'text="Login with email"',
        'text="Log in with email"',
        ':text("email"):visible',
        'a:has-text("email")',
        'button:has-text("email")',
    ],

    # --- Logged-in detection ---
    "logged_in_indicator": [
        '[class*="puppeteer_test_profile"]',
        'img[class*="avatar"]',
        '[aria-label="Profile"]',
        '[aria-label="Your profile"]',
        'a[href*="/profile/"]',
        '[class*="ProfilePhoto"]',
        '[data-functional-selector="profile-photo"]',
        '[class*="SiteHeader"] img[src*="profile"]',
    ],

    # --- Question page: open answer editor ---
    "answer_button": [
        'button:has-text("Answer")',
        '[class*="puppeteer_test_answer_button"]',
        'a:has-text("Answer")',
        '[data-functional-selector="answer-button"]',
        'button[aria-label="Answer"]',
        '.q-click-wrapper:has-text("Answer")',
        # The inline answer prompt area
        '[class*="AnswerStory"] [contenteditable="true"]',
        '[placeholder*="Write your answer"]',
    ],

    # --- Answer editor (rich text contenteditable) ---
    "answer_editor": [
        # Quora uses a contenteditable div inside the answer composer
        '[class*="puppeteer_test_answer_composer"] [contenteditable="true"]',
        '[class*="AnswerComposer"] [contenteditable="true"]',
        '.doc [contenteditable="true"]',
        '[role="textbox"][contenteditable="true"]',
        '[data-placeholder*="Write your answer"] [contenteditable="true"]',
        '[data-placeholder*="Write your answer"]',
        '[class*="CKEditor"] [contenteditable="true"]',
        '[class*="editor"] [contenteditable="true"]',
        # Broader fallback — first visible contenteditable
        '[contenteditable="true"]:visible',
    ],

    # --- Submit / Post answer button ---
    "post_submit_button": [
        '[class*="puppeteer_test_submit_button"]',
        'button:has-text("Post")',
        'button:has-text("Submit")',
        'button[data-functional-selector="submit-button"]',
        '[class*="SubmitButton"] button',
        # Quora sometimes wraps in a q-click-wrapper
        '.q-click-wrapper button:has-text("Post")',
        '.q-click-wrapper button:has-text("Submit")',
        'button[type="submit"]:visible',
    ],

    # --- CAPTCHA detection ---
    "captcha_indicator": [
        'iframe[src*="captcha"]',
        'iframe[src*="recaptcha"]',
        'iframe[src*="hcaptcha"]',
        '[class*="captcha"]',
        '[id*="captcha"]',
        '[class*="Captcha"]',
        '#recaptcha',
        '.g-recaptcha',
        '[data-sitekey]',
    ],

    # --- Error / restriction detection ---
    "error_indicator": [
        '[class*="puppeteer_test_error"]',
        '[class*="ErrorMessage"]',
        '[role="alert"]',
        '[class*="error_message"]',
        '.qu-color--red_error',
        '[class*="FormError"]',
    ],

    # --- Account restriction / ban detection ---
    "restriction_indicator": [
        'text="Your account has been"',
        'text="restricted"',
        'text="suspended"',
        'text="temporarily blocked"',
        'text="violated"',
        '[class*="BanNotice"]',
        '[class*="RestrictedNotice"]',
    ],

    # --- Topic page: question links ---
    "topic_question_links": [
        '[class*="puppeteer_test_question_title"] a',
        'a[class*="question_link"]',
        '.q-click-wrapper a[href*="/"]',
        'span[class*="QuestionText"] a',
        'a[href]:has(span[class*="q-text"])',
    ],

    # --- "Read more" / "Continue reading" button ---
    "read_more_button": [
        '[class*="puppeteer_test_read_more_button"]',
        'button:has-text("Continue Reading")',
        'button:has-text("(more)")',
    ],
}


async def _find_element(page: Page, selector_key: str, timeout: int = 5000):
    """Try multiple selectors for an element, return the first match.

    Args:
        page: Playwright page
        selector_key: Key into the SELECTORS dict
        timeout: Max ms to wait per selector attempt (short to fail fast)

    Returns:
        Element handle or None
    """
    selectors = SELECTORS.get(selector_key, [])
    for selector in selectors:
        try:
            element = await page.wait_for_selector(selector, timeout=timeout, state="visible")
            if element:
                logger.debug(f"[{selector_key}] matched: {selector}")
                return element
        except PlaywrightTimeout:
            continue
        except Exception as e:
            logger.debug(f"[{selector_key}] selector '{selector}' error: {e}")
            continue
    return None


async def _detect_issue(page: Page) -> str | None:
    """Check if there's a CAPTCHA, error, or restriction on the page.

    Returns a description string if an issue is found, None otherwise.
    """
    captcha = await _find_element(page, "captcha_indicator", timeout=1000)
    if captcha:
        return "captcha"

    restriction = await _find_element(page, "restriction_indicator", timeout=1000)
    if restriction:
        text = await restriction.inner_text()
        return f"restriction: {text[:100]}"

    error = await _find_element(page, "error_indicator", timeout=1000)
    if error:
        text = await error.inner_text()
        return f"error: {text[:100]}"

    return None


async def _screenshot(page: Page, name: str):
    """Take a debug screenshot."""
    try:
        path = SCREENSHOTS_DIR / f"{name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        await page.screenshot(path=str(path), full_page=False)
        logger.info(f"Screenshot saved: {path}")
    except Exception as e:
        logger.debug(f"Screenshot failed: {e}")


# ---------------------------------------------------------------------------
# Login
# ---------------------------------------------------------------------------


async def login_to_quora(page: Page, email: str, password: str) -> bool:
    """Log in to Quora with the given credentials.

    Strategy:
    1. Navigate to Quora homepage
    2. Check if already logged in via session cookies
    3. If not, find and click "Login with email" if present
    4. Fill email + password fields
    5. Submit and verify login success
    6. Handle CAPTCHA/restriction detection
    """
    try:
        await page.goto("https://www.quora.com/", wait_until="domcontentloaded", timeout=30000)
        await human_like_delay(page, 2000, 4000)

        # Check if already logged in
        logged_in = await _find_element(page, "logged_in_indicator", timeout=3000)
        if logged_in:
            logger.info(f"Already logged in as {email}")
            return True

        # Check for issues before attempting login
        issue = await _detect_issue(page)
        if issue:
            logger.warning(f"Issue detected before login for {email}: {issue}")
            await _screenshot(page, f"pre_login_issue_{email}")
            return False

        # Try clicking "Login with email" link if the email field isn't visible yet
        email_field = await _find_element(page, "login_email_input", timeout=2000)
        if not email_field:
            email_link = await _find_element(page, "login_with_email_link", timeout=3000)
            if email_link:
                await email_link.click()
                await human_like_delay(page, 1500, 3000)
            else:
                logger.warning(f"Cannot find email login option for {email}")
                await _screenshot(page, f"no_email_login_{email}")
                return False

        # Find and fill email
        email_field = await _find_element(page, "login_email_input", timeout=5000)
        if not email_field:
            logger.error(f"Email input not found for {email}")
            await _screenshot(page, f"no_email_field_{email}")
            return False

        await email_field.click()
        await human_like_delay(page, 300, 600)
        # Clear any existing text first
        await page.keyboard.press("Control+a")
        await page.keyboard.press("Backspace")
        # Type email with human-like speed
        for char in email:
            await page.keyboard.type(char, delay=random.randint(40, 100))

        await human_like_delay(page, 500, 1000)

        # Find and fill password
        password_field = await _find_element(page, "login_password_input", timeout=5000)
        if not password_field:
            logger.error(f"Password input not found for {email}")
            await _screenshot(page, f"no_password_field_{email}")
            return False

        await password_field.click()
        await human_like_delay(page, 200, 500)
        for char in password:
            await page.keyboard.type(char, delay=random.randint(30, 80))

        await human_like_delay(page, 500, 1200)

        # Submit login
        submit = await _find_element(page, "login_submit_button", timeout=5000)
        if submit:
            await submit.click()
        else:
            # Fallback: press Enter
            await page.keyboard.press("Enter")

        await human_like_delay(page, 3000, 6000)

        # Wait for navigation
        try:
            await page.wait_for_load_state("networkidle", timeout=15000)
        except PlaywrightTimeout:
            pass  # Page may not reach full networkidle

        # Check for post-login issues
        issue = await _detect_issue(page)
        if issue:
            logger.warning(f"Issue after login attempt for {email}: {issue}")
            await _screenshot(page, f"post_login_issue_{email}")
            return False

        # Verify login
        logged_in = await _find_element(page, "logged_in_indicator", timeout=5000)
        if logged_in:
            logger.info(f"Successfully logged in as {email}")
            return True

        logger.warning(f"Login verification failed for {email}")
        await _screenshot(page, f"login_unverified_{email}")
        return False

    except Exception as e:
        logger.error(f"Login error for {email}: {e}")
        await _screenshot(page, f"login_exception_{email}")
        return False


# ---------------------------------------------------------------------------
# Post answer
# ---------------------------------------------------------------------------


async def post_answer(page: Page, question_url: str, answer_text: str) -> dict:
    """Navigate to a Quora question and post an answer.

    Returns a dict with:
        success (bool): Whether posting succeeded
        error (str): Error description if failed
        screenshot (str): Path to debug screenshot if any
    """
    result = {"success": False, "error": "", "screenshot": ""}

    try:
        # Navigate to question
        await page.goto(question_url, wait_until="domcontentloaded", timeout=30000)
        await human_like_delay(page, 2000, 4000)

        # Check for page-level issues
        issue = await _detect_issue(page)
        if issue:
            result["error"] = issue
            await _screenshot(page, "page_issue")
            return result

        # Simulate reading the question (scroll naturally)
        for _ in range(random.randint(2, 5)):
            scroll_amount = random.randint(150, 400)
            await page.evaluate(f"window.scrollBy(0, {scroll_amount})")
            await human_like_delay(page, 800, 2000)

        # Scroll back to top where the answer button usually is
        await page.evaluate("window.scrollTo(0, 0)")
        await human_like_delay(page, 500, 1000)

        # Step 1: Open the answer editor
        answer_btn = await _find_element(page, "answer_button", timeout=8000)
        if answer_btn:
            # Check if it's already a contenteditable (inline answer area)
            is_editable = await answer_btn.get_attribute("contenteditable")
            if is_editable == "true":
                # The answer area is already open/inline, just click to focus
                await answer_btn.click()
            else:
                await answer_btn.click()
                await human_like_delay(page, 2000, 4000)
        else:
            # Sometimes the editor is already visible on the page
            logger.info("No explicit answer button found, looking for editor directly")

        # Step 2: Find the answer editor
        editor = await _find_element(page, "answer_editor", timeout=8000)
        if not editor:
            result["error"] = "Could not find answer editor"
            await _screenshot(page, "no_editor")
            logger.error(f"Answer editor not found on {question_url}")
            return result

        # Focus the editor
        await editor.click()
        await human_like_delay(page, 500, 1000)

        # Clear any placeholder text
        await page.keyboard.press("Control+a")
        await page.keyboard.press("Backspace")
        await human_like_delay(page, 200, 400)

        # Step 3: Type the answer with human-like behavior
        paragraphs = answer_text.split("\n\n")
        for i, paragraph in enumerate(paragraphs):
            lines = paragraph.split("\n")
            for j, line in enumerate(lines):
                # Handle bold text markers (**text**)
                parts = line.split("**")
                for k, part in enumerate(parts):
                    if k % 2 == 1:
                        # Bold text: use Ctrl+B
                        await page.keyboard.press("Control+b")
                        await page.keyboard.type(part, delay=random.randint(15, 50))
                        await page.keyboard.press("Control+b")
                    else:
                        await page.keyboard.type(part, delay=random.randint(15, 50))

                # Line break within paragraph
                if j < len(lines) - 1:
                    await page.keyboard.press("Shift+Enter")
                    await human_like_delay(page, 100, 300)

            # Paragraph break
            if i < len(paragraphs) - 1:
                await page.keyboard.press("Enter")
                await human_like_delay(page, 300, 800)

            # Occasional pause to simulate thinking
            if random.random() < 0.15:
                await human_like_delay(page, 1500, 4000)

        # Step 4: Review pause (human would re-read before posting)
        await human_like_delay(page, 3000, 7000)

        # Step 5: Submit the answer
        submit = await _find_element(page, "post_submit_button", timeout=8000)
        if not submit:
            result["error"] = "Could not find submit/post button"
            await _screenshot(page, "no_submit")
            logger.error("Submit button not found")
            return result

        # Scroll to ensure submit button is visible
        await submit.scroll_into_view_if_needed()
        await human_like_delay(page, 500, 1000)
        await submit.click()
        await human_like_delay(page, 3000, 6000)

        # Wait for the post to be processed
        try:
            await page.wait_for_load_state("networkidle", timeout=15000)
        except PlaywrightTimeout:
            pass

        # Step 6: Verify success
        issue = await _detect_issue(page)
        if issue:
            result["error"] = issue
            await _screenshot(page, "post_issue")
            return result

        # Check if the answer appeared on the page
        # After successful post, Quora typically shows the answer inline
        # We can check if our answer text appears in the page
        page_content = await page.content()
        # Check for a snippet of our answer (first 50 chars, cleaned)
        snippet = answer_text[:50].replace("**", "").strip()
        if snippet and snippet in page_content:
            logger.info(f"Answer verified on page: {question_url}")
        else:
            logger.info(f"Answer submitted to {question_url} (could not verify inline)")

        result["success"] = True
        logger.info(f"Successfully posted answer to {question_url}")
        return result

    except Exception as e:
        result["error"] = str(e)
        logger.error(f"Error posting answer to {question_url}: {e}")
        await _screenshot(page, "post_exception")
        return result


# ---------------------------------------------------------------------------
# Browser state persistence
# ---------------------------------------------------------------------------


async def save_browser_state(context: BrowserContext, profile_path: str):
    """Save cookies and localStorage for session persistence across runs."""
    try:
        state = await context.storage_state()
        state_path = Path(profile_path) / "state.json"
        state_path.parent.mkdir(parents=True, exist_ok=True)
        with open(state_path, "w") as f:
            json.dump(state, f, indent=2)
        logger.info(f"Browser state saved to {state_path}")
    except Exception as e:
        logger.error(f"Failed to save browser state: {e}")


async def load_browser_state(profile_path: str) -> str | None:
    """Return the storage state file path if it exists."""
    state_path = Path(profile_path) / "state.json"
    if state_path.exists():
        return str(state_path)
    return None


# ---------------------------------------------------------------------------
# Topic page scraping helpers
# ---------------------------------------------------------------------------


async def extract_questions_from_page(page: Page) -> list[dict[str, str]]:
    """Extract question URLs and titles from the current Quora page.

    Works on topic pages, search results, and the home feed.
    """
    questions = []
    seen_urls = set()

    # Try each selector strategy for question links
    for selector in SELECTORS["topic_question_links"]:
        try:
            links = await page.query_selector_all(selector)
            for link in links:
                href = await link.get_attribute("href")
                if not href:
                    continue

                # Normalize URL
                if href.startswith("/"):
                    href = f"https://www.quora.com{href}"

                if "quora.com/" not in href or href in seen_urls:
                    continue

                path = href.split("quora.com/")[-1].split("?")[0].strip("/")
                # Filter: questions have hyphens and aren't profiles/topics/spaces
                skip_prefixes = ("profile/", "topic/", "spaces/", "q/", "about/", "search/", "answer/")
                if path and "-" in path and not path.startswith(skip_prefixes):
                    text = await link.inner_text()
                    title = text.strip() if text.strip() else path.replace("-", " ")
                    if len(title) > 10:
                        questions.append({
                            "url": f"https://www.quora.com/{path}",
                            "title": title[:500],
                        })
                        seen_urls.add(href)
        except Exception:
            continue

    # Fallback: extract all links and filter
    if not questions:
        try:
            all_links = await page.query_selector_all('a[href*="quora.com/"]')
            for link in all_links:
                href = await link.get_attribute("href") or ""
                if href.startswith("/"):
                    href = f"https://www.quora.com{href}"

                if href in seen_urls or "quora.com/" not in href:
                    continue

                path = href.split("quora.com/")[-1].split("?")[0].strip("/")
                skip_prefixes = ("profile/", "topic/", "spaces/", "q/", "about/", "search/", "answer/")
                if path and "-" in path and not path.startswith(skip_prefixes):
                    text = await link.inner_text()
                    title = text.strip() if text.strip() else path.replace("-", " ")
                    if len(title) > 10:
                        questions.append({
                            "url": f"https://www.quora.com/{path}",
                            "title": title[:500],
                        })
                        seen_urls.add(href)
        except Exception as e:
            logger.debug(f"Fallback link extraction error: {e}")

    logger.info(f"Extracted {len(questions)} questions from page")
    return questions
