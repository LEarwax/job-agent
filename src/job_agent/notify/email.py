import base64
from dataclasses import dataclass
from datetime import datetime
from email.mime.text import MIMEText

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from job_agent.config import settings
from job_agent.models import Application, Job


@dataclass
class PipelineRunSummary:
    discovered: int = 0
    scored_kept: int = 0
    scored_skipped: int = 0
    pending_review: list[Job] = None        # jobs awaiting user review
    outreach_drafts: dict[int, str] = None  # job_id → drafted LinkedIn message

    def __post_init__(self):
        if self.pending_review is None:
            self.pending_review = []
        if self.outreach_drafts is None:
            self.outreach_drafts = {}

SCOPES = ["https://www.googleapis.com/auth/gmail.send"]


def _get_gmail_service():
    """Loads cached OAuth token and returns an authenticated Gmail service."""
    token_path = settings.gmail_token_path
    if not token_path.exists():
        raise FileNotFoundError(
            f"Gmail token not found at {token_path}. "
            "Run `job-agent auth-gmail` to complete OAuth setup."
        )
    creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)
    return build("gmail", "v1", credentials=creds)


def send_pipeline_summary(summary: PipelineRunSummary) -> None:
    """Sends a nightly digest email with discovery + scoring results."""
    service = _get_gmail_service()
    run_time = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

    lines = [
        f"Job Agent — Nightly Run Summary",
        f"{'=' * 40}",
        f"Run time:  {run_time}",
        f"",
        f"Discovered:      {summary.discovered} new jobs",
        f"Passed scoring:  {summary.scored_kept}",
        f"Skipped (low fit): {summary.scored_skipped}",
        f"",
    ]

    if summary.pending_review:
        lines.append(f"Pending Your Review ({len(summary.pending_review)} jobs):")
        lines.append("-" * 40)
        for job in summary.pending_review:
            from job_agent.outreach.message import linkedin_search_urls
            recruiters_url, managers_url = linkedin_search_urls(job.company)
            draft = summary.outreach_drafts.get(job.id, "")

            lines.append(f"\n{'─' * 40}")
            lines.append(f"{job.title} @ {job.company}")
            lines.append(f"Score:  {job.fit_score}/10 — {job.fit_reason}")
            lines.append(f"URL:    {job.url}")
            lines.append(f"")
            lines.append(f"Find contacts:")
            lines.append(f"  Recruiters:       {recruiters_url}")
            lines.append(f"  Eng managers:     {managers_url}")
            if draft:
                lines.append(f"")
                lines.append(f"Suggested LinkedIn message:")
                lines.append(f"  {draft}")
        lines.append(f"\n{'─' * 40}")
        lines.append("")
        lines.append("Run `job-agent review` to approve jobs for tailoring.")
    else:
        lines.append("No new jobs pending review.")

    body = "\n".join(lines)
    message = MIMEText(body)
    message["to"] = settings.application_email
    message["subject"] = f"[job-agent] {summary.scored_kept} jobs to review — {run_time[:10]}"

    encoded = base64.urlsafe_b64encode(message.as_bytes()).decode()
    service.users().messages().send(userId="me", body={"raw": encoded}).execute()


def send_application_confirmation(job: Job, application: Application) -> None:
    """Sends a confirmation email to the dedicated applications inbox."""
    service = _get_gmail_service()

    body = (
        f"Application Submitted\n"
        f"{'=' * 40}\n\n"
        f"Role:      {job.title}\n"
        f"Company:   {job.company}\n"
        f"ATS:       {job.ats_provider.value}\n"
        f"URL:       {job.url}\n"
        f"Submitted: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}\n"
        f"Resume:    {application.resume_path or 'base resume'}\n\n"
        f"Resume Changes:\n{application.tailoring_notes or 'None'}\n"
    )

    message = MIMEText(body)
    message["to"] = settings.application_email
    message["subject"] = f"Applied: {job.title} @ {job.company}"

    encoded = base64.urlsafe_b64encode(message.as_bytes()).decode()
    service.users().messages().send(userId="me", body={"raw": encoded}).execute()
