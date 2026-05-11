from pathlib import Path
from typing import Optional

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build


SCOPES = ["https://www.googleapis.com/auth/drive"]

BASE_DIR = Path(__file__).resolve().parents[1]
TOKEN_PATH = BASE_DIR / "secrets" / "google_drive_token.json"

ROOT_FOLDER_NAME = "Bible Translation"
INBOX_FOLDER_NAME = "01_inbox_ocr"


def get_drive_service():
    creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)
    return build("drive", "v3", credentials=creds)


def find_folder(service, folder_name: str, parent_id: Optional[str] = None):
    query_parts = [
        f"name = '{folder_name}'",
        "mimeType = 'application/vnd.google-apps.folder'",
        "trashed = false",
    ]

    if parent_id:
        query_parts.append(f"'{parent_id}' in parents")

    query = " and ".join(query_parts)

    result = service.files().list(
        q=query,
        spaces="drive",
        fields="files(id, name, mimeType, webViewLink)",
        pageSize=10,
    ).execute()

    folders = result.get("files", [])

    if not folders:
        return None

    return folders[0]


def list_files_in_folder(service, folder_id: str):
    query = f"'{folder_id}' in parents and trashed = false"

    result = service.files().list(
        q=query,
        spaces="drive",
        fields="files(id, name, mimeType, modifiedTime, size, webViewLink)",
        pageSize=50,
        orderBy="modifiedTime desc",
    ).execute()

    return result.get("files", [])


def main():
    service = get_drive_service()

    root_folder = find_folder(service, ROOT_FOLDER_NAME)

    if not root_folder:
        print(f"Root folder not found: {ROOT_FOLDER_NAME}")
        return

    print("Root folder found:")
    print(f"- name: {root_folder['name']}")
    print(f"- id: {root_folder['id']}")

    inbox_folder = find_folder(
        service=service,
        folder_name=INBOX_FOLDER_NAME,
        parent_id=root_folder["id"],
    )

    if not inbox_folder:
        print(f"Inbox folder not found: {INBOX_FOLDER_NAME}")
        return

    print("\nInbox folder found:")
    print(f"- name: {inbox_folder['name']}")
    print(f"- id: {inbox_folder['id']}")

    files = list_files_in_folder(service, inbox_folder["id"])

    print(f"\nTask files count: {len(files)}")

    for file in files:
        print("\nTask file:")
        print(f"- name: {file.get('name')}")
        print(f"- id: {file.get('id')}")
        print(f"- mimeType: {file.get('mimeType')}")
        print(f"- modifiedTime: {file.get('modifiedTime')}")
        print(f"- webViewLink: {file.get('webViewLink')}")


if __name__ == "__main__":
    main()
