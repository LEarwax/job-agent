import feedparser

from job_agent.discovery.base import BaseDiscoverer
from job_agent.models import ATSProvider, Job


def _detect_ats(url: str) -> ATSProvider:
    if "greenhouse.io" in url:
        return ATSProvider.GREENHOUSE
    if "lever.co" in url:
        return ATSProvider.LEVER
    if "workday.com" in url or "myworkdayjobs.com" in url:
        return ATSProvider.WORKDAY
    if "ashbyhq.com" in url:
        return ATSProvider.ASHBY
    return ATSProvider.UNKNOWN


class IndeedDiscoverer(BaseDiscoverer):
    """Discovers jobs via Indeed RSS feeds."""

    source_name = "indeed"

    def __init__(self, query: str, location: str):
        self.query = query
        self.location = location
        self.feed_url = (
            f"https://www.indeed.com/rss?"
            f"q={query.replace(' ', '+')}&l={location.replace(' ', '+')}"
        )

    async def discover(self) -> list[Job]:
        feed = feedparser.parse(self.feed_url)
        jobs = []
        for entry in feed.entries:
            company = "Unknown"
            if hasattr(entry, "source") and hasattr(entry.source, "title"):
                company = entry.source.title

            url = entry.link
            job = Job(
                title=entry.title,
                company=company,
                url=url,
                source=self.source_name,
                description=entry.get("summary", ""),
                ats_provider=_detect_ats(url),
            )
            jobs.append(job)
        return jobs
