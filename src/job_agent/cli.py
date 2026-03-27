import asyncio

import typer
from rich.console import Console
from rich.table import Table

app = typer.Typer(help="AI-powered job application agent", no_args_is_help=True)
console = Console()


@app.command()
def run(
    discover_only: bool = typer.Option(False, "--discover-only", help="Only discover new jobs"),
    tailor_only: bool = typer.Option(False, "--tailor-only", help="Only tailor resumes for discovered jobs"),
    apply_only: bool = typer.Option(False, "--apply-only", help="Only submit approved applications"),
) -> None:
    """Run the full pipeline or a specific stage."""
    from job_agent.agent.orchestrator import run_discovery, run_tailoring, run_applications, run_pipeline
    from job_agent.db import init_db

    init_db()

    if discover_only:
        from job_agent.agent.orchestrator import run_scoring
        from job_agent.notify.email import PipelineRunSummary, send_pipeline_summary
        from job_agent.models import ApplicationStatus, Job
        from job_agent.db import engine
        from sqlmodel import Session, select

        discovered = asyncio.run(run_discovery())
        kept, skipped = asyncio.run(run_scoring())

        from job_agent.outreach.message import draft_outreach_message

        with Session(engine) as session:
            pending = session.exec(
                select(Job).where(Job.status == ApplicationStatus.DISCOVERED)
            ).all()
            pending = list(pending)

        console.print(f"  Drafting outreach messages for {len(pending)} jobs...")
        outreach_drafts = {}
        for job in pending:
            try:
                outreach_drafts[job.id] = draft_outreach_message(job)
            except Exception:
                pass  # non-fatal — digest still sends without the message

        summary = PipelineRunSummary(
            discovered=discovered,
            scored_kept=kept,
            scored_skipped=skipped,
            pending_review=pending,
            outreach_drafts=outreach_drafts,
        )
        try:
            send_pipeline_summary(summary)
            console.print("[green]Summary email sent.[/green]")
        except Exception as e:
            console.print(f"[yellow]Email failed (check auth-gmail): {e}[/yellow]")
    elif tailor_only:
        asyncio.run(run_tailoring())
    elif apply_only:
        asyncio.run(run_applications())
    else:
        asyncio.run(run_pipeline())


@app.command()
def apply() -> None:
    """Submit all approved applications via automated browser."""
    from job_agent.agent.orchestrator import run_applications
    from job_agent.db import init_db

    init_db()
    asyncio.run(run_applications())


@app.command()
def review(
    pdfs: bool = typer.Option(False, "--pdfs", help="Review tailored PDFs before submission instead of pre-tailor job review"),
) -> None:
    """Review jobs before tailoring, or review PDFs before submission (--pdfs)."""
    from job_agent.db import init_db
    from job_agent.review.gate import review_discovered_jobs, review_pending_applications

    init_db()
    if pdfs:
        review_pending_applications()
    else:
        review_discovered_jobs()


@app.command()
def status() -> None:
    """Show a count of applications by status."""
    from sqlmodel import Session, func, select

    from job_agent.db import engine, init_db
    from job_agent.models import Application, ApplicationStatus

    init_db()

    table = Table(title="Application Pipeline Status")
    table.add_column("Status", style="cyan")
    table.add_column("Count", justify="right", style="bold")

    with Session(engine) as session:
        for s in ApplicationStatus:
            count = session.exec(
                select(func.count(Application.id)).where(Application.status == s)
            ).one()
            color = {
                "submitted": "green",
                "failed": "red",
                "skipped": "dim",
                "approved": "yellow",
            }.get(s.value, "white")
            table.add_row(f"[{color}]{s.value}[/{color}]", str(count))

    console.print(table)


@app.command(name="batch-process")
def batch_process() -> None:
    """Check and process a pending batch API tailoring job."""
    from job_agent.agent.orchestrator import process_pending_batch
    from job_agent.db import init_db

    init_db()
    asyncio.run(process_pending_batch())


@app.command(name="auth-gmail")
def auth_gmail() -> None:
    """Run the one-time Gmail OAuth flow to authorize sending emails."""
    from google_auth_oauthlib.flow import InstalledAppFlow

    from job_agent.config import settings

    SCOPES = ["https://www.googleapis.com/auth/gmail.send"]

    if not settings.gmail_credentials_path.exists():
        console.print(
            f"[red]Gmail credentials not found at {settings.gmail_credentials_path}[/red]\n"
            "Download your OAuth 2.0 credentials JSON from Google Cloud Console and place it there."
        )
        raise typer.Exit(1)

    flow = InstalledAppFlow.from_client_secrets_file(
        str(settings.gmail_credentials_path), SCOPES
    )
    creds = flow.run_local_server(port=0)

    settings.gmail_token_path.parent.mkdir(parents=True, exist_ok=True)
    settings.gmail_token_path.write_text(creds.to_json())
    console.print(f"[green]Gmail authorized. Token saved to {settings.gmail_token_path}[/green]")


if __name__ == "__main__":
    app()
