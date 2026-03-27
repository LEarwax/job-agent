# Job Agent — Technical Specification

## Overview

An AI-powered job application agent that discovers relevant postings, tailors your resume for each one,
routes you through a human review gate, and submits applications automatically through supported ATS portals.

---

## MVP Scope

### In Scope
- Job discovery via Indeed RSS feeds
- Resume tailoring via Claude API (keyword optimization, bullet reordering — no fabrication)
- Human-in-the-loop review gate (CLI)
- Automated application submission for **Greenhouse** and **Lever** (friendliest ATS platforms)
- Email confirmation to a dedicated inbox via Gmail API
- SQLite-backed state (dedup, status tracking)

### Out of Scope (V1)
- Workday automation (significant anti-bot measures; slated for V2 with Computer Use API)
- LinkedIn scraping (ToS risk; use RSS/email alerts instead)
- Multi-user support
- Dashboard/web UI
- Pre-employment assessments / essay questions

---

## Architecture

```
┌──────────────────────────────────────────────────────────┐
│                     CLI (Typer)                          │
└───────────────────────────┬──────────────────────────────┘
                            │
                ┌───────────▼───────────┐
                │     Orchestrator      │
                │  (agent/orchestrator) │
                └─────┬──────┬──────────┘
                      │      │
          ┌───────────▼─┐  ┌─▼────────────┐
          │  Discovery  │  │    Resume    │
          │  (Indeed    │  │   Tailor     │
          │   RSS)      │  │ (Claude API) │
          └───────┬─────┘  └──────┬───────┘
                  │               │
          ┌───────▼───────────────▼───────┐
          │           SQLite DB           │
          │  (jobs, applications, state)  │
          └───────────────┬───────────────┘
                          │
               ┌──────────▼──────────┐
               │    Review Gate      │
               │    (CLI / Rich)     │
               └──────────┬──────────┘
                          │
          ┌───────────────▼──────────────┐
          │      Application Agent       │
          │  Playwright + ATS Applicators│
          │  (Greenhouse, Lever)         │
          └───────────────┬──────────────┘
                          │
               ┌──────────▼──────────┐
               │   Email Notify      │
               │   (Gmail API)       │
               └─────────────────────┘
```

---

## Tech Stack

| Layer | Library | Rationale |
|-------|---------|-----------|
| Language | Python 3.12+ | Best AI/scraping ecosystem; directly maps to AWS boto3 |
| LLM | `anthropic` | Claude API for resume tailoring; Computer Use for V2 |
| Browser | `playwright` | More reliable than Selenium; async-native |
| Database | `sqlmodel` | SQLAlchemy + Pydantic in one; easy upgrade path to Postgres/RDS |
| Config | `pydantic-settings` | .env-backed settings with type safety |
| CLI | `typer` + `rich` | Clean CLI with pretty output |
| Email | `google-api-python-client` | Gmail API for sending confirmation emails |
| Feed parsing | `feedparser` | Indeed RSS discovery |
| Scheduling | `apscheduler` | V2: run pipeline on a cron schedule |

---

## Data Models

### Job
| Field | Type | Notes |
|-------|------|-------|
| id | int (PK) | auto |
| title | str | |
| company | str | |
| url | str (unique) | dedup key |
| source | str | indeed, linkedin, etc. |
| description | str | full job description |
| ats_provider | enum | greenhouse, lever, workday, ashby, direct, unknown |
| discovered_at | datetime | |
| status | enum | see ApplicationStatus |

### Application
| Field | Type | Notes |
|-------|------|-------|
| id | int (PK) | auto |
| job_id | int (FK) | |
| resume_path | str | path to tailored resume file |
| tailoring_notes | str | what Claude changed and why |
| status | enum | see ApplicationStatus |
| created_at | datetime | |
| submitted_at | datetime | null until submitted |
| error_message | str | populated on failure |
| email_sent | bool | |

### ApplicationStatus (enum)
`discovered → pending_review → approved → submitted`
                                         `→ failed`
                          `→ skipped`

---

## Key Flows

### 1. Discovery
1. For each `(target_role, target_location)` pair, fetch Indeed RSS
2. Parse entries, dedup by URL against SQLite
3. Save new `Job` records with status `discovered`

### 2. Resume Tailoring
1. For each `Job` with status `discovered`:
   - Load base resume text
   - Send to Claude with structured prompt (reorder/rephrase only, no fabrication)
   - Save tailored version to `data/resumes/tailored/{job_id}_{company}.txt`
   - Create `Application` record with status `pending_review`
   - Update `Job` status to `pending_review`

### 3. Review Gate
1. Load all `Application` records with status `pending_review`
2. Display job details + resume changes in Rich table
3. User approves → status `approved`; declines → status `skipped`

### 4. Application Submission
1. For each `Application` with status `approved`:
   - Detect ATS provider from URL
   - Route to appropriate `BaseApplicator` subclass
   - Run Playwright automation
   - On success: status `submitted`, send Gmail confirmation
   - On failure: status `failed`, log error

---

## Known Limitations & Mitigations

| Limitation | Impact | Mitigation |
|-----------|--------|------------|
| Indeed RSS has limited fields | Missing salary, full description | Follow link to scrape full posting detail |
| Greenhouse/Lever form variability | Occasional automation failures | Fallback: flag for manual + log URL |
| Resume is plain text in V1 | Loses formatting | V2: use `python-docx` for .docx round-trip |
| Gmail OAuth requires initial setup | First-run friction | One-time consent flow, token cached after |
| No Workday support | Misses many postings | V2: Claude Computer Use API |
| Claude may exceed tailoring constraints | Hallucinated experience | Strict system prompt + post-validation diff |

---

## V2 Roadmap

- **Workday support** via Claude Computer Use API
- **LinkedIn discovery** via job alert email parsing
- **Scheduled runs** via APScheduler (poll every N hours)
- **Web review UI** instead of CLI gate
- **PDF resume support** via `pypdf` + `reportlab`
- **Salary/fit scoring** before tailoring (skip low-fit postings automatically)
- **AWS deployment**: Lambda + EventBridge for scheduling, RDS for DB, S3 for resume storage
