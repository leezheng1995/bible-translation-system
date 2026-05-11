from fastapi import APIRouter

from app.services.google_drive_client import GoogleDriveClient


router = APIRouter(
    prefix="/drive",
    tags=["drive"],
)


@router.get("/health")
def drive_health():
    client = GoogleDriveClient()

    root_folder = client.get_root_folder()
    inbox_folder = client.get_inbox_folder()

    return {
        "status": "ok",
        "root_folder": root_folder,
        "inbox_folder": inbox_folder,
    }


@router.get("/tasks")
def list_drive_tasks():
    client = GoogleDriveClient()
    tasks = client.list_inbox_tasks()

    return {
        "count": len(tasks),
        "tasks": tasks,
    }
