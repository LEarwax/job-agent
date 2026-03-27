import subprocess
from datetime import datetime

from rich.console import Console
from rich.prompt import Prompt
from rich.table import Table
from sqlmodel import Session, select

from job_agent.db import engine
from job_agent.models import Application, ApplicationStatus, Job

console = Console()


def review_discovered_jobs() -> tuple[int, int]:
    """
    Pre-tailor review: shows DISCOVERED jobs with fit scores.
    User approves jobs worth tailoring, skips the rest.
    Returns (approved, skipped) counts.
    """
    with Session(engine) as session:
        jobs = session.exec(select(Job).where(Job.status == ApplicationStatus.DISCOVERED)).all()

        if not jobs:
            console.print("[yellow]No jobs pending review.[/yellow]")
            return 0, 0

        console.print(f"\n[bold cyan]Jobs Pending Review: {len(jobs)}[/bold cyan]\n")
        approved = skipped = 0

        for job in jobs:
            table = Table(title=f"[bold]{job.title} @ {job.company}[/bold]", show_header=False)
            table.add_column("Field", style="cyan", width=20)
            table.add_column("Value")
            table.add_row("Company", job.company)
            table.add_row("Role", job.title)
            table.add_row("Source", job.source)
            table.add_row("ATS", job.ats_provider.value)
            table.add_row("Fit Score", f"{job.fit_score}/10" if job.fit_score else "n/a")
            table.add_row("Fit Reason", job.fit_reason or "")
            table.add_row("URL", job.url)
            console.print(table)
            console.print()

            choice = Prompt.ask(
                "  [a]pprove for tailoring  [s]kip",
                choices=["a", "s"],
                default="s",
            )

            if choice == "a":
                job.status = ApplicationStatus.APPROVED
                approved += 1
                console.print("  [green]Approved — will be tailored.[/green]\n")
            else:
                job.status = ApplicationStatus.SKIPPED
                skipped += 1
                console.print("  [yellow]Skipped.[/yellow]\n")

            session.add(job)
            session.commit()

    console.print(f"[bold]Review complete. Approved: {approved} | Skipped: {skipped}[/bold]")
    return approved, skipped

def _open_file(path: str) -> None:
    subprocess.Popen(["open", path])


def _open_url(url: str) -> None:
    subprocess.Popen(["open", url])


def review_pending_applications() -> list[int]:
    """
    Presents all pending applications for human review via the CLI.

    Options per application:
      a  — approve for automated submission
      m  — manual: open PDF + job URL in browser, mark as submitted
      s  — skip

    Returns list of approved application IDs.
    """
    approved_ids: list[int] = []

    with Session(engine) as session:
        applications = session.exec(
            select(Application).where(Application.status == ApplicationStatus.PENDING_REVIEW)
        ).all()

        if not applications:
            console.print("[yellow]No applications pending review.[/yellow]")
            return []

        console.print(f"\n[bold cyan]Applications Pending Review: {len(applications)}[/bold cyan]\n")

        for app in applications:
            job = session.get(Job, app.job_id)
            if job is None:
                continue

            table = Table(title=f"[bold]#{app.id} — {job.title} @ {job.company}[/bold]", show_header=False)
            table.add_column("Field", style="cyan", width=20)
            table.add_column("Value")
            table.add_row("Company", job.company)
            table.add_row("Role", job.title)
            table.add_row("ATS", job.ats_provider.value)
            table.add_row("URL", job.url)
            table.add_row("Resume", app.resume_path or "base resume")
            table.add_row("Changes", app.tailoring_notes or "none")
            console.print(table)

            # Auto-open the PDF so they can review it
            if app.resume_path and app.resume_path.endswith(".pdf"):
                _open_file(app.resume_path)

            console.print()
            choice = Prompt.ask(
                "  [a]pprove (auto-submit)  [m]anual (open & mark done)  [s]kip",
                choices=["a", "m", "s"],
                default="s",
            )

            if choice == "a":
                app.status = ApplicationStatus.APPROVED
                approved_ids.append(app.id)
                console.print("  [green]Approved for automated submission.[/green]\n")

            elif choice == "m":
                _open_url(job.url)
                app.status = ApplicationStatus.SUBMITTED
                app.submitted_at = datetime.utcnow()
                job.status = ApplicationStatus.SUBMITTED
                session.add(job)
                console.print("  [blue]Opened in browser. Marked as manually submitted.[/blue]\n")

            else:
                app.status = ApplicationStatus.SKIPPED
                console.print("  [yellow]Skipped.[/yellow]\n")

            session.add(app)
            session.commit()

    console.print(f"[bold]Review complete. Approved for auto-submit: {len(approved_ids)}[/bold]")
    return approved_ids
