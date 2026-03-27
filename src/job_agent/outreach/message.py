"""
Generates personalized LinkedIn outreach messages and search URLs for
recruiters and hiring managers at companies with relevant job postings.
"""

from urllib.parse import quote_plus

import anthropic

from job_agent.config import settings
from job_agent.models import Job

# Always use Haiku — message drafting is a low-complexity generation task.
DRAFTING_MODEL = "claude-haiku-4-5-20251001"

SYSTEM_PROMPT = """You write short LinkedIn outreach messages for a job seeker.

Candidate background:
- Full-stack software engineer, 6+ years experience
- Primary stack: C#, .NET Core, ASP.NET Core, REST APIs, SQL Server
- Secondary: Angular, TypeScript
- Looking for senior/lead backend or full-stack roles, remote

Write a 2-3 sentence message that:
- Feels natural and human, not templated
- References the specific role and company by name
- Highlights the one most relevant skill match for this role
- Ends with a low-pressure ask (connect, quick chat, etc.)

Return only the message text. No subject line, no greeting placeholder, no sign-off."""

_client: anthropic.Anthropic | None = None


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    return _client


def draft_outreach_message(job: Job) -> str:
    """Returns a personalized LinkedIn message for this job's company."""
    response = _get_client().messages.create(
        model=DRAFTING_MODEL,
        max_tokens=200,
        system=SYSTEM_PROMPT,
        messages=[
            {
                "role": "user",
                "content": (
                    f"Role: {job.title}\n"
                    f"Company: {job.company}\n\n"
                    f"Job Description (excerpt):\n{job.description[:1000]}"
                ),
            }
        ],
    )
    return response.content[0].text.strip()


def linkedin_search_urls(company: str) -> tuple[str, str]:
    """
    Returns (recruiters_url, managers_url) LinkedIn people search URLs
    for the given company.
    """
    encoded = quote_plus(company)
    recruiters = (
        f"https://www.linkedin.com/search/results/people/"
        f"?keywords=technical+recruiter+{encoded}&origin=GLOBAL_SEARCH_HEADER"
    )
    managers = (
        f"https://www.linkedin.com/search/results/people/"
        f"?keywords=engineering+manager+{encoded}&origin=GLOBAL_SEARCH_HEADER"
    )
    return recruiters, managers
