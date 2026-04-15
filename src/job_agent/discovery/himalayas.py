import httpx

from job_agent.discovery.base import BaseDiscoverer
from job_agent.discovery.indeed import _detect_ats
from job_agent.models import Job


class HimalayasDiscoverer(BaseDiscoverer):
    """Discovers jobs via the Himalayas remote job board API."""

    source_name = "himalayas"
    API_URL = "https://himalayas.app/jobs/api"

    async def discover(self) -> list[Job]:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(self.API_URL, params={"limit": 100})
            resp.raise_for_status()
            data = resp.json()

        jobs = []
        for item in data.get("jobs", []):
            url = item.get("applicationLink") or item.get("url", "")
            if not url:
                continue
            jobs.append(
                Job(
                    title=item.get("title", ""),
                    company=item.get("companyName", "Unknown"),
                    url=url,
                    source=self.source_name,
                    description=item.get("description", ""),
                    ats_provider=_detect_ats(url),
                )
            )
        return jobs
