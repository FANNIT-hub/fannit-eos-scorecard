"""Google Sheets API v4 client.

Auth via Application Default Credentials. In Cloud Run this resolves to the
runtime service account (eos-scorecard-runtime@...). Locally it falls back
to user credentials via gcloud auth application-default login.
"""

from functools import lru_cache

from google.auth import default
from googleapiclient.discovery import build

SCOPES = ("https://www.googleapis.com/auth/spreadsheets",)


@lru_cache(maxsize=1)
def get_sheets_service():
    credentials, _project = default(scopes=list(SCOPES))
    return build("sheets", "v4", credentials=credentials, cache_discovery=False)
