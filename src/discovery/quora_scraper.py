"""Discover questions by scraping Quora topic pages directly using Playwright.

This module navigates to Quora topic pages and extracts question URLs.
It uses Playwright with anti-detection measures to avoid being blocked.
"""

import logging
import random
import re

from src.config import settings

logger = logging.getLogger(__name__)

# Quora topic page URLs for EEC's key areas
QUORA_TOPIC_URLS = {
    "test_prep": [
        "https://www.quora.com/topic/IELTS",
        "https://www.quora.com/topic/PTE-Academic",
        "https://www.quora.com/topic/GRE-Test",
        "https://www.quora.com/topic/TOEFL",
        "https://www.quora.com/topic/SAT-Exam",
        "https://www.quora.com/topic/Duolingo-English-Test",
        "https://www.quora.com/topic/OET-Occupational-English-Test",
        "https://www.quora.com/topic/Test-Preparation",
    ],
    "study_abroad": [
        "https://www.quora.com/topic/Studying-Abroad",
        "https://www.quora.com/topic/Study-in-Canada",
        "https://www.quora.com/topic/Study-in-the-UK",
        "https://www.quora.com/topic/Study-in-USA",
        "https://www.quora.com/topic/Study-in-Australia",
        "https://www.quora.com/topic/Study-in-Germany",
        "https://www.quora.com/topic/MBA-Admissions",
        "https://www.quora.com/topic/Master-of-Science-MS-Degree",
    ],
    "visa": [
        "https://www.quora.com/topic/Student-Visas",
        "https://www.quora.com/topic/Visa-Applications",
        "https://www.quora.com/topic/Immigration",
    ],
    "education_loan": [
        "https://www.quora.com/topic/Education-Loans",
        "https://www.quora.com/topic/Student-Loans",
    ],
}


async def scrape_quora_topic_page(
    page,  # Playwright page object
    topic_url: str,
    category: str,
    max_questions: int = 20,
    scroll_count: int = 3,
) -> list[dict[str, str]]:
    """Scrape a Quora topic page for question URLs.

    Args:
        page: Playwright page instance (already logged in or anonymous)
        topic_url: URL of the Quora topic page
        category: Category tag for discovered questions
        max_questions: Maximum number of questions to extract
        scroll_count: Number of times to scroll down for infinite-scroll loading

    Returns:
        List of dicts with url, title, category
    """
    results = []
    seen_urls = set()

    try:
        await page.goto(topic_url, wait_until="domcontentloaded", timeout=30000)
        await page.wait_for_timeout(random.randint(2000, 4000))

        # Scroll to load more questions (Quora uses infinite scroll)
        for _ in range(scroll_count):
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await page.wait_for_timeout(random.randint(1500, 3000))

        # Extract question links
        links = await page.query_selector_all('a[href]')

        for link in links:
            href = await link.get_attribute("href")
            if not href:
                continue

            # Normalize URL
            if href.startswith("/"):
                href = f"https://www.quora.com{href}"

            # Filter for question pages
            if "quora.com/" not in href:
                continue

            path = href.split("quora.com/")[-1].split("?")[0].strip("/")

            # Questions have hyphens and don't start with known non-question prefixes
            if (
                path
                and "-" in path
                and not path.startswith(("profile/", "topic/", "spaces/", "q/", "about/", "search/"))
                and href not in seen_urls
            ):
                # Try to get the question text
                text = await link.inner_text()
                title = text.strip() if text.strip() else path.replace("-", " ")

                # Clean up title
                title = re.sub(r"\s+", " ", title).strip()

                if len(title) > 10:  # Skip very short/empty titles
                    results.append({
                        "url": f"https://www.quora.com/{path}",
                        "title": title,
                        "category": category,
                    })
                    seen_urls.add(href)

            if len(results) >= max_questions:
                break

        logger.info(f"Scraped {len(results)} questions from {topic_url}")

    except Exception as e:
        logger.error(f"Failed to scrape topic page {topic_url}: {e}")

    return results


async def scrape_all_topics(
    page,
    max_per_topic: int = 10,
) -> list[dict[str, str]]:
    """Scrape all configured Quora topic pages.

    Args:
        page: Playwright page instance
        max_per_topic: Max questions to extract per topic page

    Returns:
        Deduplicated list of discovered questions
    """
    all_results = []
    seen_urls = set()

    for category, urls in QUORA_TOPIC_URLS.items():
        for url in urls:
            questions = await scrape_quora_topic_page(
                page=page,
                topic_url=url,
                category=category,
                max_questions=max_per_topic,
            )

            for q in questions:
                if q["url"] not in seen_urls:
                    seen_urls.add(q["url"])
                    all_results.append(q)

            # Human-like delay between topic pages
            delay = random.randint(3000, 8000)
            await page.wait_for_timeout(delay)

    logger.info(f"Total questions discovered from topic pages: {len(all_results)}")
    return all_results
