"""Discover Quora questions via Google site: search.

Uses Google search with site:quora.com to find relevant questions.
This is more reliable than scraping Quora directly because Google
indexes Quora pages and provides structured results.
"""

import logging
import random
import re
import time
from urllib.parse import quote_plus, urlparse

import httpx
from bs4 import BeautifulSoup

from src.config import settings

logger = logging.getLogger(__name__)

# Rotate user agents to avoid blocks
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
]


def _extract_quora_urls(html: str) -> list[dict[str, str]]:
    """Parse Google search results HTML to extract Quora question URLs and titles."""
    soup = BeautifulSoup(html, "html.parser")
    results = []

    for link in soup.find_all("a", href=True):
        href = link["href"]

        # Extract URL from Google's redirect wrapper
        if "/url?q=" in href:
            match = re.search(r"/url\?q=(https?://[^&]+)", href)
            if match:
                href = match.group(1)

        # Filter for Quora question pages
        parsed = urlparse(href)
        if parsed.netloc in ("www.quora.com", "quora.com") and "/" in parsed.path:
            path = parsed.path.strip("/")
            # Quora question URLs are like /What-is-the-best-way-to-prepare-for-IELTS
            # Skip profile pages, topic pages, spaces
            if (
                path
                and not path.startswith("profile/")
                and not path.startswith("topic/")
                and not path.startswith("spaces/")
                and not path.startswith("q/")
                and "-" in path  # Questions have hyphens
            ):
                clean_url = f"https://www.quora.com/{path}"
                title = _url_path_to_title(path)

                # Try to get a better title from surrounding text
                parent = link.find_parent()
                if parent:
                    h3 = parent.find("h3")
                    if h3:
                        title = h3.get_text(strip=True)
                        # Remove "- Quora" suffix
                        title = re.sub(r"\s*-\s*Quora\s*$", "", title)

                if clean_url not in [r["url"] for r in results]:
                    results.append({"url": clean_url, "title": title})

    return results


def _url_path_to_title(path: str) -> str:
    """Convert a Quora URL path to a readable title."""
    # Remove the leading path component if it's a topic
    parts = path.split("/")
    question_part = parts[-1] if parts else path
    return question_part.replace("-", " ")


async def search_google_for_quora_questions(
    keyword: str,
    category: str,
    max_results: int = 10,
    recent_only: bool = True,
) -> list[dict[str, str]]:
    """Search Google for Quora questions matching a keyword.

    Args:
        keyword: Search term (e.g., "IELTS preparation tips")
        category: Question category for tagging (e.g., "test_prep")
        max_results: Maximum number of results to return
        recent_only: If True, limit to results from the past year

    Returns:
        List of dicts with keys: url, title, category
    """
    query = f'site:quora.com "{keyword}"'
    if recent_only:
        query += " &tbs=qdr:y"  # Past year

    encoded_query = quote_plus(query)
    url = f"https://www.google.com/search?q={encoded_query}&num={max_results}"

    headers = {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    }

    try:
        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            response = await client.get(url, headers=headers)
            response.raise_for_status()

        results = _extract_quora_urls(response.text)

        # Tag each result with category
        for r in results:
            r["category"] = category

        logger.info(f"Found {len(results)} Quora questions for keyword '{keyword}'")
        return results[:max_results]

    except httpx.HTTPError as e:
        logger.error(f"Google search failed for '{keyword}': {e}")
        return []


async def discover_questions_batch(
    max_per_keyword: int = 5,
) -> list[dict[str, str]]:
    """Run discovery across all configured keyword categories.

    Returns deduplicated list of discovered questions.
    """
    all_results: list[dict[str, str]] = []
    seen_urls: set[str] = set()

    for category, keywords in settings.discovery_keywords.items():
        for keyword in keywords:
            results = await search_google_for_quora_questions(
                keyword=keyword,
                category=category,
                max_results=max_per_keyword,
            )

            for r in results:
                if r["url"] not in seen_urls:
                    seen_urls.add(r["url"])
                    all_results.append(r)

            # Random delay between searches to avoid rate limiting
            delay = random.uniform(2.0, 5.0)
            logger.debug(f"Sleeping {delay:.1f}s between searches")
            time.sleep(delay)

    logger.info(f"Discovery batch complete: {len(all_results)} unique questions found")
    return all_results
