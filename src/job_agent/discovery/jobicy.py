import feedparser

from job_agent.discovery.base import BaseDiscoverer
from job_agent.discovery.indeed import _detect_ats
from job_agent.models import Job


class JobicyDiscoverer(BaseDiscoverer):
    """Discovers jobs via the Jobicy remote jobs RSS feed."""

    source_name = "jobicy"
    FEED_URL = (
        "https://jobicy.com/?feed=job_feed"
        "&num_jobs=50&region=anywhere&jobType=full-time"
    )

    async def discover(self) -> list[Job]:
        feed = feedparser.parse(self.FEED_URL)
        jobs = []
        for entry in feed.entries:
            url = entry.get("link", "")
            if not url:
                continue
            # Jobicy puts the company name in the author field
            company = entry.get("author") or "Unknown"
            jobs.append(
                Job(
                    title=entry.get("title", ""),
                    company=company,
                    url=url,
                    source=self.source_name,
                    description=entry.get("summary", ""),
                    ats_provider=_detect_ats(url),
                )
            )
        return jobs
