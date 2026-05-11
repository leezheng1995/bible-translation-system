from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
    )

    app_env: str = "local"
    app_name: str = "bible-translation-system"
    app_port: int = 8000

    celery_broker_url: str = "redis://redis:6379/0"
    celery_result_backend: str = "redis://redis:6379/1"
    database_url: str = "sqlite:///./data/bible_translation.db"

    ollama_base_url: str = "http://host.docker.internal:11434"
    ollama_translation_model: str = "qwen3:14b"
    ollama_review_model: str = "gemma4:26b"
    ollama_default_model: str = "qwen3:14b"
    ollama_embedding_model: str = "bge-m3"

    google_drive_root_folder_name: str = "Bible Translation"
    google_drive_inbox_folder_name: str = "01_inbox_ocr"
    google_drive_processing_folder_name: str = "02_processing"
    google_drive_archive_folder_name: str = "03_archive"
    google_drive_failed_folder_name: str = "04_failed"
    google_drive_token_path: str = "/app/secrets/google_drive_token.json"


@lru_cache
def get_settings() -> Settings:
    return Settings()
