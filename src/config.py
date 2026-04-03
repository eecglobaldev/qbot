"""Central configuration for the EEC Quora Bot."""

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # API Keys
    anthropic_api_key: str = ""

    # Database
    database_url: str = "sqlite+aiosqlite:///data/qbot.db"

    # Dashboard
    dashboard_host: str = "0.0.0.0"
    dashboard_port: int = 8000
    dashboard_secret_key: str = "change-this-to-a-random-string"

    # Proxy
    proxy_url: str = ""

    # Discovery
    discovery_interval_minutes: int = 60
    max_questions_per_run: int = 50

    # Posting safety limits
    max_posts_per_account_per_day: int = 3
    min_delay_between_posts_seconds: int = 1800
    max_delay_between_posts_seconds: int = 7200

    # Logging
    log_level: str = "INFO"

    # Paths
    project_root: Path = Field(default_factory=lambda: Path(__file__).parent.parent)

    # Answer generation
    answer_min_words: int = 200
    answer_max_words: int = 800
    claude_model: str = "claude-sonnet-4-20250514"

    # Question discovery keywords organized by category
    @property
    def discovery_keywords(self) -> dict[str, list[str]]:
        return {
            "test_prep": [
                "IELTS preparation", "IELTS tips", "IELTS coaching",
                "PTE Academic tips", "PTE preparation", "PTE coaching",
                "GRE preparation", "GRE study plan", "GRE tips",
                "TOEFL preparation", "TOEFL tips", "TOEFL coaching",
                "Duolingo English Test", "Duolingo test tips",
                "CELPIP preparation", "CELPIP tips",
                "SAT preparation", "SAT tips", "SAT coaching",
                "LanguageCert preparation",
                "OET preparation", "OET tips", "OET nursing",
                "D-SAT preparation",
            ],
            "study_abroad": [
                "study abroad", "study in USA", "study in UK",
                "study in Canada", "study in Australia", "study in Germany",
                "study in Ireland", "study in New Zealand",
                "MBA abroad", "MS abroad", "MBBS abroad",
                "Masters in Management abroad", "MiM programs",
                "undergraduate abroad", "bachelor degree abroad",
                "university admission abroad", "SOP writing",
                "statement of purpose tips",
            ],
            "visa": [
                "student visa", "spouse visa", "tourist visa",
                "visa extension", "visa application tips",
                "student visa USA", "student visa Canada",
                "student visa UK", "student visa Australia",
                "visa interview tips",
            ],
            "language": [
                "spoken English classes", "improve English speaking",
                "learn French", "French classes India",
                "learn German", "German classes India",
                "English fluency tips",
            ],
            "education_loan": [
                "education loan abroad", "education loan study abroad",
                "student loan India", "education loan for MS",
                "education loan for MBA abroad",
            ],
        }


settings = Settings()
