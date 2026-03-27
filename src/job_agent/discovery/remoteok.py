import feedparser

from job_agent.discovery.base import BaseDiscoverer
from job_agent.discovery.indeed import _detect_ats
from job_agent.models import Job


class RemoteOKDiscoverer(BaseDiscoverer):
    """Discovers jobs via RemoteOK RSS feed."""

    source_name = "remoteok"
    FEED_URL = "https://remoteok.com/remote-dev-jobs.rss"

    async def discover(self) -> list[Job]:
        feed = feedparser.parse(self.FEED_URL)
        jobs = []
        for entry in feed.entries:
            url = entry.get("link", "")
            company = entry.get("author") or entry.get("company") or "Unknown"
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