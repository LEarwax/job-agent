from datetime import datetime
from enum import Enum
from typing import Optional

from sqlmodel import Field, SQLModel


class ApplicationStatus(str, Enum):
    DISCOVERED = "discovered"
    PENDING_REVIEW = "pending_review"
    APPROVED = "approved"
    SUBMITTED = "submitted"
    FAILED = "failed"
    SKIPPED = "skipped"


class ATSProvider(str, Enum):
    GREENHOUSE = "greenhouse"
    LEVER = "lever"
    WORKDAY = "workday"
    ASHBY = "ashby"
    DIRECT = "direct"
    UNKNOWN = "unknown"


class Job(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    title: str
    company: str
    url: str = Field(unique=True, index=True)
    source: str
    description: str
    ats_provider: ATSProvider = ATSProvider.UNKNOWN
    discovered_at: datetime = Field(default_factory=datetime.utcnow)
    status: ApplicationStatus = ApplicationStatus.DISCOVERED
    fit_score: Optional[int] = None
    fit_reason: Optional[str] = None


class Application(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    job_id: int = Field(foreign_key="job.id", index=True)
    resume_path: Optional[str] = None
    tailoring_notes: Optional[str] = None
    status: ApplicationStatus = ApplicationStatus.PENDING_REVIEW
    created_at: datetime = Field(default_factory=datetime.utcnow)
    submitted_at: Optional[datetime] = None
    error_message: Optional[str] = None
    email_sent: bool = False
