"""
Main pipeline orchestrator.

Flow: discover → score → tailor → review gate → apply → notify
"""

import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path

import anthropic
from playwright.async_api import async_playwright
from sqlmodel import Session, select

from job_agent.apply.greenhouse import GreenhouseApplicator
from job_agent.apply.lever import LeverApplicator
from job_agent.config import settings
from job_agent.db import engine, init_db
from job_agent.discovery.remoteok import RemoteOKDiscoverer
from job_agent.discovery.weworkremotely import WeWorkRemotelyDiscoverer, FEEDS
from job_agent.models import Application, ApplicationStatus, Job
from job_agent.notify.email import send_application_confirmation
from job_agent.resume.tailor import tailor_resume, build_batch_request, process_batch_result
from job_agent.review.gate import review_pending_applications
from job_agent.score.fit import score_job_fit

BATCH_STATE_PATH = settings.db_path.parent / "batches" / "pending.json"

APPLICATORS = [GreenhouseApplicator(), LeverApplicator()]


async def run_discovery() -> int:
    """Discover new jobs across all configured sources. Returns count of new jobs."""
    discoverers = [
        RemoteOKDiscoverer(),
        *[WeWorkRemotelyDiscoverer(feed) for feed in FEEDS],
    ]

    total_new = 0
    with Session(engine) as session:
        for discoverer in discoverers:
            jobs = await discoverer.discover()
            new_count = 0
            for job in jobs:
                existing = session.exec(select(Job).where(Job.url == job.url)).first()
                if existing:
                    continue
                # Also deduplicate by (company, title) — job boards frequently
                # re-post the same listing with a new URL/tracking ID.
                duplicate = session.exec(
                    select(Job).where(
                        Job.company == job.company,
                        Job.title == job.title,
                    )
                ).first()
                if not duplicate:
                    if discoverer.is_relevant(job, settings.target_roles, settings.exclude_title_keywords):
                        session.add(job)
                        new_count += 1
            session.commit()
            print(f"  [{discoverer.source_name}] {new_count} new jobs")
            total_new += new_count

    return total_new


async def run_scoring() -> tuple[int, int]:
    """
    Score all DISCOVERED jobs for fit. Jobs below MIN_FIT_SCORE are marked SKIPPED.
    Returns (kept, skipped) counts.
    """
    kept = skipped = 0
    with Session(engine) as session:
        jobs = session.exec(
            select(Job).where(
                Job.status == ApplicationStatus.DISCOVERED,
                Job.fit_score == None,  # noqa: E711
            )
        ).all()
        for job in jobs:
            score, reason = score_job_fit(job)
            job.fit_score = score
            job.fit_reason = reason
            if score < settings.min_fit_score:
                job.status = ApplicationStatus.SKIPPED
                skipped += 1
                print(f"  [score {score}/10] SKIP  {job.title} @ {job.company} — {reason}")
            else:
                kept += 1
                print(f"  [score {score}/10] KEEP  {job.title} @ {job.company} — {reason}")
            session.add(job)
        session.commit()
    return kept, skipped


async def run_tailoring() -> int:
    """
    Tailor resumes for all DISCOVERED jobs.
    - Synchronous mode (default): processes immediately, returns count.
    - Batch mode (USE_BATCH_API=true): submits to Batch API, saves state, returns 0.
    """
    if not settings.base_resume_path.exists():
        raise FileNotFoundError(
            f"Base resume not found at {settings.base_resume_path}. "
            "Export your resume as base_resume.docx and place it there."
        )

    settings.tailored_resume_dir.mkdir(parents=True, exist_ok=True)

    with Session(engine) as session:
        jobs = session.exec(select(Job).where(Job.status == ApplicationStatus.APPROVED)).all()

        if not jobs:
            return 0

        if settings.use_batch_api:
            return await _submit_tailor_batch(jobs, session)

        count = 0
        for job in jobs:
            print(f"  Tailoring resume for: {job.title} @ {job.company}")
            _, pdf_path, notes = tailor_resume(job, settings.base_resume_path)
            session.add(Application(
                job_id=job.id,
                resume_path=str(pdf_path),
                tailoring_notes=notes,
                status=ApplicationStatus.APPROVED,
            ))
            session.add(job)
            count += 1

        session.commit()
    return count


async def _submit_tailor_batch(jobs: list[Job], session: Session) -> int:
    """Submit a Messages Batch for all jobs and save state to disk. Returns 0."""
    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    requests = [build_batch_request(job, settings.base_resume_path) for job in jobs]
    batch = client.messages.batches.create(requests=requests)

    BATCH_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    BATCH_STATE_PATH.write_text(json.dumps({
        "batch_id": batch.id,
        "submitted_at": datetime.now(timezone.utc).isoformat(),
        "job_ids": [j.id for j in jobs],
    }))

    print(f"  Batch submitted: {batch.id}")
    print(f"  Run `job-agent batch-process` to check status and process results.")
    return 0


async def process_pending_batch() -> int:
    """
    Check the pending batch and process results if complete.
    Returns count of applications created, or 0 if still in progress.
    """
    if not BATCH_STATE_PATH.exists():
        print("No pending batch found.")
        return 0

    state = json.loads(BATCH_STATE_PATH.read_text())
    batch_id = state["batch_id"]
    job_ids = set(state["job_ids"])

    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    batch = client.messages.batches.retrieve(batch_id)

    if batch.processing_status == "in_progress":
        counts = batch.request_counts
        print(f"  Batch {batch_id} still in progress.")
        print(f"  Processing: {counts.processing} | Succeeded: {counts.succeeded} | Errored: {counts.errored}")
        return 0

    settings.tailored_resume_dir.mkdir(parents=True, exist_ok=True)
    count = 0

    with Session(engine) as session:
        for result in client.messages.batches.results(batch_id):
            job_id = int(result.custom_id)
            if job_id not in job_ids:
                continue
            job = session.get(Job, job_id)
            if job is None:
                continue

            if result.result.type != "succeeded":
                print(f"  ERROR for job {job_id}: {result.result.type}")
                continue

            response_text = result.result.message.content[0].text
            print(f"  Processing result: {job.title} @ {job.company}")
            _, pdf_path, notes = process_batch_result(job, response_text, settings.base_resume_path)

            session.add(Application(
                job_id=job.id,
                resume_path=str(pdf_path),
                tailoring_notes=notes,
                status=ApplicationStatus.PENDING_REVIEW,
            ))
            job.status = ApplicationStatus.PENDING_REVIEW
            session.add(job)
            count += 1

        session.commit()

    BATCH_STATE_PATH.unlink()
    print(f"  Batch complete. {count} resumes processed.")
    return count


async def run_applications() -> tuple[int, int]:
    """Submit all approved applications. Returns (submitted, failed) counts."""
    submitted = 0
    failed = 0

    with Session(engine) as session:
        approved = session.exec(
            select(Application).where(Application.status == ApplicationStatus.APPROVED)
        ).all()

        if not approved:
            print("  No approved applications to submit.")
            return 0, 0

        async with async_playwright() as p:
            # headful=True during development so you can watch and intervene
            browser = await p.chromium.launch(headless=False)

            for application in approved:
                job = session.get(Job, application.job_id)
                if job is None:
                    continue

                print(f"  Applying to: {job.title} @ {job.company}")
                page = await browser.new_page()

                try:
                    await page.goto(job.url, timeout=30_000)

                    applicator = next(
                        (a for a in APPLICATORS if await a.can_handle(job.url)), None
                    )

                    if applicator is None:
                        print(f"    No applicator for {job.ats_provider.value} — skipping")
                        application.status = ApplicationStatus.FAILED
                        application.error_message = f"No applicator for ATS: {job.ats_provider.value}"
                        failed += 1
                    else:
                        success = await applicator.apply(
                            page, job, application, application.resume_path or ""
                        )
                        if success:
                            application.status = ApplicationStatus.SUBMITTED
                            application.submitted_at = datetime.utcnow()
                            send_application_confirmation(job, application)
                            application.email_sent = True
                            submitted += 1
                            print(f"    Submitted.")
                        else:
                            application.status = ApplicationStatus.FAILED
                            failed += 1
                            print(f"    Failed (applicator returned False).")

                except NotImplementedError as e:
                    application.status = ApplicationStatus.FAILED
                    application.error_message = str(e)
                    failed += 1
                    print(f"    Skipped (not yet implemented): {e}")

                except Exception as e:
                    application.status = ApplicationStatus.FAILED
                    application.error_message = str(e)
                    failed += 1
                    print(f"    Error: {e}")

                finally:
                    session.add(application)
                    session.commit()
                    await page.close()

            await browser.close()

    return submitted, failed


async def run_pipeline() -> None:
    """Full pipeline: discover → tailor → review → apply."""
    init_db()

    print("\n=== Step 1: Discovering jobs ===")
    new_jobs = await run_discovery()
    print(f"  Total new jobs: {new_jobs}")

    print(f"\n=== Step 2: Scoring job fit (min score: {settings.min_fit_score}/10) ===")
    kept, skipped = await run_scoring()
    print(f"  Kept: {kept} | Skipped (low fit): {skipped}")

    if not settings.auto_approve:
        print("\n=== Step 3: Review gate ===")
        from job_agent.review.gate import review_discovered_jobs
        review_discovered_jobs()
    else:
        print("\n=== Step 3: Auto-approving (AUTO_APPROVE=true) ===")
        with Session(engine) as session:
            jobs = session.exec(
                select(Job).where(Job.status == ApplicationStatus.DISCOVERED)
            ).all()
            for job in jobs:
                job.status = ApplicationStatus.APPROVED
                session.add(job)
            session.commit()
            print(f"  Approved: {len(jobs)} jobs")

    print("\n=== Step 4: Tailoring resumes ===")
    tailored = await run_tailoring()
    if settings.use_batch_api:
        print("  Batch submitted — run `job-agent batch-process` when ready.")
        return
    print(f"  Tailored: {tailored} resumes")

    print("\n=== Step 5: Submitting applications ===")
    submitted, failed = await run_applications()
    print(f"  Submitted: {submitted} | Failed: {failed}")
