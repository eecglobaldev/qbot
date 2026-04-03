"""Discover Quora questions via Google site: search.

Uses Google search with site:quora.com to find relevant questions.
This is more reliable than scraping Quora directly because Google
indexes Quora pages and provides structured results.
"""

import asyncio
import logging
import random
import re
import time
from urllib.parse import quote_plus, urlparse, unquote

import httpx
from bs4 import BeautifulSoup

from src.config import settings

logger = logging.getLogger(__name__)

# Rotate user agents to avoid blocks
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:128.0) Gecko/20100101 Firefox/128.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
]


def _extract_quora_urls(html: str) -> list[dict[str, str]]:
    """Parse Google search results HTML to extract Quora question URLs and titles."""
    soup = BeautifulSoup(html, "html.parser")
    results = []
    seen_urls = set()

    # Strategy 1: Find all <a> tags and check href for quora.com
    for a_tag in soup.find_all("a", href=True):
        href = a_tag["href"]

        # Google wraps URLs in /url?q=ACTUAL_URL&...
        if "/url?q=" in href:
            match = re.search(r"/url\?q=(https?://[^&]+)", href)
            if match:
                href = unquote(match.group(1))

        # Also check direct quora URLs
        if "quora.com/" not in href:
            continue

        parsed = urlparse(href)
        if parsed.netloc not in ("www.quora.com", "quora.com"):
            continue

        path = parsed.path.strip("/")

        # Filter: questions have hyphens; skip profiles, topics, spaces
        skip_prefixes = ("profile/", "topic/", "spaces/", "q/", "about/", "search/", "answer/")
        if not path or path.startswith(skip_prefixes):
            continue

        # Questions contain hyphens (e.g., What-is-the-best-way-to-prepare-for-IELTS)
        if "-" not in path:
            continue

        clean_url = f"https://www.quora.com/{path}"
        if clean_url in seen_urls:
            continue
        seen_urls.add(clean_url)

        # Get title from the <a> tag text or parent <h3>
        title = ""
        h3 = a_tag.find("h3")
        if h3:
            title = h3.get_text(strip=True)
        elif a_tag.get_text(strip=True):
            title = a_tag.get_text(strip=True)

        # Clean up title
        title = re.sub(r"\s*-\s*Quora\s*$", "", title)
        title = re.sub(r"\s+", " ", title).strip()

        # If we couldn't get a title from the tag, derive from URL
        if not title or len(title) < 5:
            title = path.split("/")[-1].replace("-", " ")

        results.append({"url": clean_url, "title": title})

    # Strategy 2: Also look for cite elements (Google shows URLs in <cite> tags)
    if not results:
        for cite in soup.find_all("cite"):
            text = cite.get_text(strip=True)
            if "quora.com/" in text:
                # Extract the path
                match = re.search(r"quora\.com/([^\s]+)", text)
                if match:
                    path = match.group(1).strip("/")
                    if "-" in path and not path.startswith(("profile/", "topic/")):
                        clean_url = f"https://www.quora.com/{path}"
                        if clean_url not in seen_urls:
                            seen_urls.add(clean_url)
                            title = path.split("/")[-1].replace("-", " ")
                            # Try to find the associated heading
                            parent = cite.find_parent()
                            while parent and parent.name != "body":
                                h3 = parent.find("h3")
                                if h3:
                                    title = re.sub(r"\s*-\s*Quora\s*$", "", h3.get_text(strip=True))
                                    break
                                parent = parent.find_parent()
                            results.append({"url": clean_url, "title": title})

    return results


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
    # Build the query — don't include tbs in the q parameter
    query = f'site:quora.com {keyword}'
    encoded_query = quote_plus(query)

    # Build URL with tbs as a separate parameter for time filtering
    url = f"https://www.google.com/search?q={encoded_query}&num={max_results}"
    if recent_only:
        url += "&tbs=qdr:y"  # Past year — must be a separate URL parameter

    headers = {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "DNT": "1",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
        "Cache-Control": "max-age=0",
    }

    try:
        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            response = await client.get(url, headers=headers)

            # Check for rate limiting
            if response.status_code == 429:
                logger.warning(f"Google rate limited for '{keyword}' — backing off")
                return []

            if response.status_code != 200:
                logger.error(f"Google search returned {response.status_code} for '{keyword}'")
                return []

            # Check if we got a CAPTCHA/sorry page
            if "/sorry/" in str(response.url) or "unusual traffic" in response.text.lower():
                logger.warning(f"Google CAPTCHA/sorry page for '{keyword}' — stopping discovery")
                return []

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
    Uses longer delays between searches to avoid Google rate limiting.
    Stops immediately if rate limited.
    """
    all_results: list[dict[str, str]] = []
    seen_urls: set[str] = set()
    rate_limited = False

    for category, keywords in settings.discovery_keywords.items():
        if rate_limited:
            break

        for keyword in keywords:
            if rate_limited:
                break

            results = await search_google_for_quora_questions(
                keyword=keyword,
                category=category,
                max_results=max_per_keyword,
            )

            if not results and len(all_results) > 0:
                # If we were getting results and now we're not, we might be rate limited
                # Give a longer backoff
                delay = random.uniform(15.0, 25.0)
                logger.info(f"No results for '{keyword}', extended delay {delay:.0f}s")
                await asyncio.sleep(delay)
                continue

            for r in results:
                if r["url"] not in seen_urls:
                    seen_urls.add(r["url"])
                    all_results.append(r)

            # Longer delays between searches to avoid rate limiting
            # Google typically allows ~10-15 searches per minute
            delay = random.uniform(8.0, 15.0)
            logger.debug(f"Sleeping {delay:.1f}s between searches")
            await asyncio.sleep(delay)

    logger.info(f"Discovery batch complete: {len(all_results)} unique questions found")
    return all_results
