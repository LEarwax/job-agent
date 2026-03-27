from abc import ABC, abstractmethod

from job_agent.models import Job


class BaseDiscoverer(ABC):
    """Base class for all job discovery sources."""

    source_name: str = ""

    @abstractmethod
    async def discover(self) -> list[Job]:
        """Fetch new job postings. Returns unsaved Job instances."""
        ...

    def is_relevant(self, job: Job, target_roles: list[str], exclude_keywords: list[str] = []) -> bool:
        """Basic relevance filter against target role keywords and exclusion list."""
        title_lower = job.title.lower()
        if any(kw.lower() in title_lower for kw in exclude_keywords):
            return False
        return any(role.lower() in title_lower for role in target_roles)
