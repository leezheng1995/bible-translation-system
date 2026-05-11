from fastapi import APIRouter

from app.core.settings import get_settings


router = APIRouter(
    prefix="/health",
    tags=["health"],
)


@router.get("")
def health():
    settings = get_settings()

    return {
        "status": "ok",
        "app_name": settings.app_name,
        "app_env": settings.app_env,
    }


@router.get("/config")
def health_config():
    settings = get_settings()

    return {
        "app": {
            "name": settings.app_name,
            "env": settings.app_env,
            "port": settings.app_port,
        },
        "ollama": {
            "base_url": settings.ollama_base_url,
            "translation_model": settings.ollama_translation_model,
            "review_model": settings.ollama_review_model,
            "embedding_model": settings.ollama_embedding_model,
        },
        "google_drive": {
            "root_folder": settings.google_drive_root_folder_name,
            "inbox_folder": settings.google_drive_inbox_folder_name,
            "processing_folder": settings.google_drive_processing_folder_name,
            "archive_folder": settings.google_drive_archive_folder_name,
            "failed_folder": settings.google_drive_failed_folder_name,
        },
    }
