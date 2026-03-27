from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).parent.parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # Anthropic
    anthropic_api_key: str = ""
    claude_model: str = "claude-haiku-4-5-20251001"

    # Database
    db_path: Path = BASE_DIR / "data" / "jobs.db"

    # Resume
    base_resume_path: Path = BASE_DIR / "data" / "resumes" / "base_resume.docx"
    tailored_resume_dir: Path = BASE_DIR / "data" / "resumes" / "tailored"

    # Gmail
    gmail_credentials_path: Path = BASE_DIR / "credentials" / "gmail_credentials.json"
    gmail_token_path: Path = BASE_DIR / "credentials" / "gmail_token.json"
    application_email: str = ""

    # Job search
    target_roles: list[str] = ["software engineer", "backend engineer"]
    target_locations: list[str] = ["remote"]
    min_salary: int | None = None
    exclude_title_keywords: list[str] = []

    # Pipeline behavior
    auto_approve: bool = False
    min_fit_score: int = 6       # jobs scoring below this are skipped before tailoring
    use_batch_api: bool = False  # submit tailoring as a batch (50% cheaper, ~1hr latency)


settings = Settings()
