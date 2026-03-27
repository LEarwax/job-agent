"""
Fit scoring: cheap pre-filter before spending tokens on tailoring.
Always uses Haiku regardless of the configured model.
"""

import json

import anthropic

from job_agent.config import settings
from job_agent.models import Job

# Hardcoded to Haiku — scoring is a triage operation, not a quality operation.
SCORING_MODEL = "claude-haiku-4-5-20251001"

SYSTEM_PROMPT = """You evaluate job fit for a backend-focused full-stack software engineer.

Candidate profile:
- Primary stack: C#, .NET Core, ASP.NET Core, REST APIs, SQL Server
- Secondary: Angular, TypeScript
- 6+ years experience, targeting senior/lead/staff individual contributor roles
- Remote only

Scoring guide:
1–3  Poor fit — frontend-only, wrong stack entirely, junior, or purely management
4–5  Weak fit — some overlap but stack or seniority mismatch
6–7  Moderate fit — relevant skills, backend or full-stack with some .NET/C# exposure
8–10 Strong fit — .NET/C#/backend/full-stack, seniority match, remote

Return JSON only, no other text: {"score": <1-10>, "reason": "<one sentence>"}"""


_client: anthropic.Anthropic | None = None


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    return _client


def score_job_fit(job: Job) -> tuple[int, str]:
    """
    Returns (score 1-10, reason string).
    Truncates description to 2000 chars to keep token cost minimal.
    """
    response = _get_client().messages.create(
        model=SCORING_MODEL,
        max_tokens=200,
        system=SYSTEM_PROMPT,
        messages=[
            {
                "role": "user",
                "content": (
                    f"Job Title: {job.title}\n"
                    f"Company: {job.company}\n\n"
                    f"Description:\n{job.description[:2000]}"
                ),
            }
        ],
    )
    try:
        raw = response.content[0].text.strip()
        # Strip markdown code fences if present
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        data = json.loads(raw.strip())
        return int(data["score"]), str(data["reason"])
    except Exception:
        return 5, "Could not parse score — defaulting to threshold."