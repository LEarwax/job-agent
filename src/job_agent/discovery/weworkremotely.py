import feedparser

from job_agent.discovery.base import BaseDiscoverer
from job_agent.discovery.indeed import _detect_ats
from job_agent.models import Job

# All WWR RSS feeds relevant to software engineering roles
FEEDS = [
    "https://weworkremotely.com/categories/remote-programming-jobs.rss",
    "https://weworkremotely.com/categories/remote-devops-sysadmin-jobs.rss",
]


class WeWorkRemotelyDiscoverer(BaseDiscoverer):
    """Discovers jobs via We Work Remotely RSS feeds."""

    source_name = "weworkremotely"

    def __init__(self, feed_url: str):
        self.feed_url = feed_url

    async def discover(self) -> list[Job]:
        feed = feedparser.parse(self.feed_url)
        jobs = []
        for entry in feed.entries:
            url = entry.get("link", "")
            # WWR titles are formatted as "Company: Role Title"
            raw_title = entry.get("title", "")
            if ": " in raw_title:
                company, title = raw_title.split(": ", 1)
            else:
                company, title = "Unknown", raw_title

            jobs.append(
                Job(
                    title=title,
                    company=company,
                    url=url,
                    source=self.source_name,
                    description=entry.get("summary", ""),
                    ats_provider=_detect_ats(url),
                )
            )
        return jobs