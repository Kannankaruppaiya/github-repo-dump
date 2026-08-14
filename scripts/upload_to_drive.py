"""
Uploads a single file to the user's own Google Drive using an OAuth
refresh token (not a service account - personal Gmail accounts have no
service-account storage quota, so this uses the user's own quota instead).
Called by the workflow right after each hourly dump chunk is generated.
"""

import os
import sys

import google.oauth2.credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

CLIENT_ID = os.environ.get("GDRIVE_CLIENT_ID")
CLIENT_SECRET = os.environ.get("GDRIVE_CLIENT_SECRET")
REFRESH_TOKEN = os.environ.get("GDRIVE_REFRESH_TOKEN")
FOLDER_ID = os.environ.get("GDRIVE_FOLDER_ID")

if not all([CLIENT_ID, CLIENT_SECRET, REFRESH_TOKEN, FOLDER_ID]):
    print("Drive OAuth secrets not fully set, skipping Drive upload.")
    sys.exit(0)

if len(sys.argv) < 2:
    print("Usage: upload_to_drive.py <file_path>")
    sys.exit(1)

file_path = sys.argv[1]
file_name = os.path.basename(file_path)

creds = google.oauth2.credentials.Credentials(
    token=None,
    refresh_token=REFRESH_TOKEN,
    token_uri="https://oauth2.googleapis.com/token",
    client_id=CLIENT_ID,
    client_secret=CLIENT_SECRET,
    scopes=["https://www.googleapis.com/auth/drive.file"],
)

service = build("drive", "v3", credentials=creds)

metadata = {"name": file_name, "parents": [FOLDER_ID]}
media = MediaFileUpload(file_path, mimetype="application/x-ndjson", resumable=True)
uploaded = service.files().create(body=metadata, media_body=media, fields="id").execute()

print(f"Uploaded {file_name} to Google Drive (file ID: {uploaded['id']})")
