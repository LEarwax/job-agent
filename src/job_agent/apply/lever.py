from playwright.async_api import Page

from job_agent.apply.base import BaseApplicator
from job_agent.models import Application, Job


class LeverApplicator(BaseApplicator):
    """
    Handles Lever ATS application forms (jobs.lever.co).

    Lever forms are clean and consistent:
    - Name, email, phone, company, LinkedIn
    - Resume upload
    - Optional cover letter
    """

    ats_name = "lever"

    async def can_handle(self, url: str) -> bool:
        return "lever.co" in url

    async def apply(
        self,
        page: Page,
        job: Job,
        application: Application,
        resume_path: str,
    ) -> bool:
        # TODO: implement
        # Suggested approach:
        # 1. Wait for .application-form
        # 2. Fill name, email, phone fields
        # 3. Upload resume
        # 4. Submit and check for success confirmation
        raise NotImplementedError("Lever applicator not yet implemented")
