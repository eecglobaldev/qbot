"""Playwright browser management with anti-detection measures.

Manages browser instances, profiles, and stealth configuration
to minimize detection when interacting with Quora.
"""

import logging
import random
from pathlib import Path

from playwright.async_api import Browser, BrowserContext, Page, async_playwright

from src.config import settings

logger = logging.getLogger(__name__)

# Viewport sizes that match common real devices
VIEWPORTS = [
    {"width": 1920, "height": 1080},
    {"width": 1366, "height": 768},
    {"width": 1536, "height": 864},
    {"width": 1440, "height": 900},
    {"width": 1280, "height": 720},
]

# Timezone/locale combos that look natural for Indian users
LOCALES = [
    {"timezone": "Asia/Kolkata", "locale": "en-IN"},
    {"timezone": "Asia/Kolkata", "locale": "en-US"},
]

# User agents for Chrome on different platforms
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
]


async def create_stealth_context(
    browser: Browser,
    profile_path: str | None = None,
    proxy_url: str | None = None,
) -> BrowserContext:
    """Create a browser context with anti-detection settings.

    Args:
        browser: Playwright browser instance
        profile_path: Path to persistent browser profile (for cookies/sessions)
        proxy_url: Optional proxy URL (http://user:pass@host:port)

    Returns:
        Configured BrowserContext
    """
    viewport = random.choice(VIEWPORTS)
    locale_config = random.choice(LOCALES)
    user_agent = random.choice(USER_AGENTS)

    context_kwargs = {
        "viewport": viewport,
        "user_agent": user_agent,
        "locale": locale_config["locale"],
        "timezone_id": locale_config["timezone"],
        "color_scheme": "light",
        "has_touch": False,
        "java_script_enabled": True,
        "ignore_https_errors": True,
        "extra_http_headers": {
            "Accept-Language": "en-US,en;q=0.9",
            "sec-ch-ua": '"Not_A Brand";v="8", "Chromium";v="121", "Google Chrome";v="121"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Windows"',
        },
    }

    if proxy_url:
        context_kwargs["proxy"] = {"server": proxy_url}

    if profile_path:
        # Use persistent context for maintaining login sessions
        Path(profile_path).mkdir(parents=True, exist_ok=True)
        context = await browser.new_context(storage_state=profile_path + "/state.json" if Path(profile_path + "/state.json").exists() else None, **context_kwargs)
    else:
        context = await browser.new_context(**context_kwargs)

    # Inject stealth scripts to avoid detection
    await context.add_init_script("""
        // Override navigator.webdriver
        Object.defineProperty(navigator, 'webdriver', { get: () => undefined });

        // Override chrome runtime
        window.chrome = { runtime: {} };

        // Override permissions
        const originalQuery = window.navigator.permissions.query;
        window.navigator.permissions.query = (parameters) =>
            parameters.name === 'notifications'
                ? Promise.resolve({ state: Notification.permission })
                : originalQuery(parameters);

        // Override plugins length
        Object.defineProperty(navigator, 'plugins', {
            get: () => [1, 2, 3, 4, 5],
        });

        // Override languages
        Object.defineProperty(navigator, 'languages', {
            get: () => ['en-US', 'en'],
        });
    """)

    return context


async def human_like_delay(page: Page, min_ms: int = 500, max_ms: int = 2000):
    """Wait a random human-like duration."""
    delay = random.randint(min_ms, max_ms)
    await page.wait_for_timeout(delay)


async def human_like_type(page: Page, selector: str, text: str, min_delay: int = 30, max_delay: int = 120):
    """Type text with human-like random delays between keystrokes."""
    element = await page.wait_for_selector(selector, timeout=10000)
    if element:
        await element.click()
        for char in text:
            await page.keyboard.type(char, delay=random.randint(min_delay, max_delay))
            # Occasionally pause mid-typing (like a real person thinking)
            if random.random() < 0.05:
                await page.wait_for_timeout(random.randint(200, 800))


class BrowserManager:
    """Manages Playwright browser lifecycle."""

    def __init__(self):
        self._playwright = None
        self._browser: Browser | None = None

    async def start(self, headless: bool = True):
        """Launch the browser."""
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(
            headless=headless,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
                "--no-sandbox",
            ],
        )
        logger.info(f"Browser launched (headless={headless})")

    async def new_context(self, profile_path: str | None = None, proxy_url: str | None = None) -> BrowserContext:
        """Create a new stealth browser context."""
        if not self._browser:
            raise RuntimeError("Browser not started. Call start() first.")
        return await create_stealth_context(self._browser, profile_path, proxy_url)

    async def stop(self):
        """Close the browser and cleanup."""
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()
        logger.info("Browser stopped")

    @property
    def browser(self) -> Browser | None:
        return self._browser
