from typing import Any, Dict, List, Optional

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from app.core.settings import get_settings


SCOPES = ["https://www.googleapis.com/auth/drive"]


class GoogleDriveClient:
    def __init__(self) -> None:
        settings = get_settings()

        self.token_path = settings.google_drive_token_path
        self.root_folder_name = settings.google_drive_root_folder_name
        self.inbox_folder_name = settings.google_drive_inbox_folder_name
        self.processing_folder_name = settings.google_drive_processing_folder_name
        self.archive_folder_name = settings.google_drive_archive_folder_name
        self.failed_folder_name = settings.google_drive_failed_folder_name

        self.service = self._build_service()

    def _build_service(self):
        creds = Credentials.from_authorized_user_file(
            self.token_path,
            SCOPES,
        )
        return build("drive", "v3", credentials=creds)

    def find_folder(
        self,
        folder_name: str,
        parent_id: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        query_parts = [
            f"name = '{folder_name}'",
            "mimeType = 'application/vnd.google-apps.folder'",
            "trashed = false",
        ]

        if parent_id:
            query_parts.append(f"'{parent_id}' in parents")

        query = " and ".join(query_parts)

        result = self.service.files().list(
            q=query,
            spaces="drive",
            fields="files(id, name, mimeType, webViewLink)",
            pageSize=10,
        ).execute()

        folders = result.get("files", [])

        if not folders:
            return None

        return folders[0]

    def get_root_folder(self) -> Optional[Dict[str, Any]]:
        return self.find_folder(self.root_folder_name)

    def get_inbox_folder(self) -> Optional[Dict[str, Any]]:
        root_folder = self.get_root_folder()

        if not root_folder:
            return None

        return self.find_folder(
            folder_name=self.inbox_folder_name,
            parent_id=root_folder["id"],
        )

    def list_inbox_tasks(self) -> List[Dict[str, Any]]:
        inbox_folder = self.get_inbox_folder()

        if not inbox_folder:
            return []

        query = f"'{inbox_folder['id']}' in parents and trashed = false"

        result = self.service.files().list(
            q=query,
            spaces="drive",
            fields="files(id, name, mimeType, modifiedTime, size, webViewLink)",
            pageSize=50,
            orderBy="modifiedTime desc",
        ).execute()

        files = result.get("files", [])

        return [
            {
                "id": file.get("id"),
                "name": file.get("name"),
                "mime_type": file.get("mimeType"),
                "modified_time": file.get("modifiedTime"),
                "size": file.get("size"),
                "web_view_link": file.get("webViewLink"),
                "status": "discovered",
            }
            for file in files
        ]
