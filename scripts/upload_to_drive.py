"""
Uploads a single file to a Google Drive folder using a service account.
Called by the workflow right after each hourly dump chunk is generated.
"""

import json
import os
import sys

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

SA_KEY = os.environ.get("GDRIVE_SA_KEY")
FOLDER_ID = os.environ.get("GDRIVE_FOLDER_ID")

if not SA_KEY or not FOLDER_ID:
    print("GDRIVE_SA_KEY or GDRIVE_FOLDER_ID not set, skipping Drive upload.")
    sys.exit(0)

if len(sys.argv) < 2:
    print("Usage: upload_to_drive.py <file_path>")
    sys.exit(1)

file_path = sys.argv[1]
file_name = os.path.basename(file_path)

creds_info = json.loads(SA_KEY)
creds = service_account.Credentials.from_service_account_info(
    creds_info, scopes=["https://www.googleapis.com/auth/drive.file"]
)
service = build("drive", "v3", credentials=creds)

metadata = {"name": file_name, "parents": [FOLDER_ID]}
media = MediaFileUpload(file_path, mimetype="application/x-ndjson", resumable=True)
uploaded = service.files().create(body=metadata, media_body=media, fields="id").execute()

print(f"Uploaded {file_name} to Google Drive (file ID: {uploaded['id']})")
