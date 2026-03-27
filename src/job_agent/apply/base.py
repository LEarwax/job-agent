from abc import ABC, abstractmethod

from playwright.async_api import Page

from job_agent.models import Application, Job


class BaseApplicator(ABC):
    """Base class for ATS-specific application automation."""

    ats_name: str = ""

    @abstractmethod
    async def can_handle(self, url: str) -> bool:
        """Returns True if this applicator handles the given ATS URL."""
        ...

    @abstractmethod
    async def apply(
        self,
        page: Page,
        job: Job,
        application: Application,
        resume_path: str,
    ) -> bool:
        """
        Executes the application flow on an already-navigated Playwright page.
        Returns True on successful submission, False on recoverable failure.
        Raises on unrecoverable errors.
        """
        ...
