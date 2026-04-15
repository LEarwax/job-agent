"""
Discovers jobs from the monthly "Ask HN: Who is hiring?" thread.

Uses the Algolia HN Search API to find the latest thread and parse
top-level comments as job postings. Each comment becomes one Job record,
using the HN item URL as the stable dedup key.
"""

import re
from html.parser import HTMLParser

import httpx

from job_agent.discovery.base import BaseDiscoverer
from job_agent.discovery.indeed import _detect_ats
from job_agent.models import Job

ALGOLIA_SEARCH = "https://hn.algolia.com/api/v1/search"
ALGOLIA_ITEMS = "https://hn.algolia.com/api/v1/items/{id}"


class _HTMLStripper(HTMLParser):
    def __init__(self):
        super().__init__()
        self._parts: list[str] = []

    def handle_data(self, data: str) -> None:
        self._parts.append(data)

    def get_text(self) -> str:
        return "\n".join(p.strip() for p in self._parts if p.strip())


def _strip_html(html: str) -> str:
    stripper = _HTMLStripper()
    stripper.feed(html or "")
    return stripper.get_text()


def _parse_comment(comment_text: str) -> tuple[str, str]:
    """
    Extract (company, title) from a HN hiring comment.

    The first line of most HN hiring posts follows one of:
      - "Company | Role | Location | ..."
      - "Company (YC S24) | Role | ..."
      - Free-form prose starting with the company name.

    Returns ("Unknown", "") if parsing fails.
    """
    first_line = comment_text.strip().splitlines()[0] if comment_text.strip() else ""
    parts = [p.strip() for p in re.split(r"\s*\|\s*", first_line) if p.strip()]
    if len(parts) >= 2:
        return parts[0], parts[1]
    if parts:
        return parts[0], ""
    return "Unknown", ""


class HNHiringDiscoverer(BaseDiscoverer):
    """Discovers jobs from the latest Ask HN: Who is hiring? thread."""

    source_name = "hn_hiring"

    async def discover(self) -> list[Job]:
        async with httpx.AsyncClient(timeout=15) as client:
            # Find the latest monthly thread
            search_resp = await client.get(
                ALGOLIA_SEARCH,
                params={
                    "query": "Ask HN: Who is hiring?",
                    "tags": "story,ask_hn",
                    "hitsPerPage": 5,
                },
            )
            search_resp.raise_for_status()
            hits = search_resp.json().get("hits", [])
            if not hits:
                return []

            thread_id = hits[0]["objectID"]

            # Fetch all top-level comments (each is one job post)
            items_resp = await client.get(ALGOLIA_ITEMS.format(id=thread_id))
            items_resp.raise_for_status()
            thread = items_resp.json()

        jobs = []
        for child in thread.get("children", []):
            text_html = child.get("text") or ""
            text = _strip_html(text_html)
            if not text:
                continue

            company, title = _parse_comment(text)
            # Use the HN item URL as the stable dedup key
            item_id = child.get("id")
            url = f"https://news.ycombinator.com/item?id={item_id}"

            jobs.append(
                Job(
                    title=title or "Software Engineer",
                    company=company,
                    url=url,
                    source=self.source_name,
                    description=text,
                    ats_provider=_detect_ats(url),
                )
            )
        return jobs
