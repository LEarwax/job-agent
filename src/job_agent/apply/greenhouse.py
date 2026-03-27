from playwright.async_api import Page

from job_agent.apply.base import BaseApplicator
from job_agent.models import Application, Job


class GreenhouseApplicator(BaseApplicator):
    """
    Handles Greenhouse ATS application forms (boards.greenhouse.io).

    Greenhouse forms are relatively consistent:
    - Name, email, phone
    - Resume upload
    - Optional LinkedIn / portfolio fields
    - Custom questions (text boxes)
    """

    ats_name = "greenhouse"

    async def can_handle(self, url: str) -> bool:
        return "greenhouse.io" in url

    async def apply(
        self,
        page: Page,
        job: Job,
        application: Application,
        resume_path: str,
    ) -> bool:
        # TODO: implement
        # Suggested approach:
        # 1. Wait for #application_form
        # 2. Fill first_name, last_name, email, phone
        # 3. Upload resume via input[type=file]
        # 4. Handle any custom required questions (pass to Claude for short answers)
        # 5. Submit and confirm success message
        raise NotImplementedError("Greenhouse applicator not yet implemented")
