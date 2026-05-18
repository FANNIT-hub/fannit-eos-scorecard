"""Secret Manager accessor.

In Cloud Run the runtime SA has secretAccessor on each project secret.
Locally, falls back to gcloud-authenticated ADC. Values are cached for the
life of the process (secrets rotate rarely; a redeploy / cold start picks
up new versions).
"""

import os
from functools import lru_cache

from google.auth import default
from google.cloud import secretmanager

_PROJECT = os.environ.get("GCP_PROJECT", "fannit-eos-scorecard")


@lru_cache(maxsize=1)
def _client() -> secretmanager.SecretManagerServiceClient:
    creds, _ = default()
    return secretmanager.SecretManagerServiceClient(credentials=creds)


@lru_cache(maxsize=32)
def get_secret(name: str, version: str = "latest") -> str:
    """Returns the secret payload as a stripped string.

    Raises google.api_core.exceptions.* on access failure so callers can
    decide whether a missing secret is fatal (it usually isn't — graceful
    degradation renders the affected KPI as null).
    """
    path = f"projects/{_PROJECT}/secrets/{name}/versions/{version}"
    resp = _client().access_secret_version(name=path)
    return resp.payload.data.decode("utf-8").strip()
