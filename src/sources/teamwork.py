"""Teamwork source: Clients in Onboarding.

Single shared instance (fannit.teamwork.com). A "client in onboarding" is an
active project whose Category == the agency's category AND which carries the
"Onboarding" tag (id 117305).

This is a SNAPSHOT metric: the API only knows the *current* state, so the
weekly snapshot job stamps today's count into the current week's cell.
Historical weeks keep whatever count was captured at the time.

Auth: Teamwork API token used as the Basic-auth username (password can be
anything, conventionally 'x').
"""

from __future__ import annotations

import base64
import logging

import requests

from ..config import (
    TEAMWORK_AGENCY_CATEGORY_ID,
    TEAMWORK_DOMAIN,
    TEAMWORK_ONBOARDING_TAG_ID,
)
from .secrets import get_secret

log = logging.getLogger("eos-scorecard.teamwork")

HTTP_TIMEOUT = 30


def _auth_header() -> dict:
    token = get_secret("teamwork-api-token")
    basic = base64.b64encode(f"{token}:x".encode()).decode()
    return {"Authorization": f"Basic {basic}", "Accept": "application/json"}


def onboarding_count(agency: str) -> int | None:
    """Count of active onboarding projects for the agency, or None on failure.

    Filters server-side by category + tag + status, then re-verifies the tag
    client-side in case the API's tag filter is loose.
    """
    cat_id = TEAMWORK_AGENCY_CATEGORY_ID.get(agency)
    if cat_id is None:
        return None

    url = f"https://{TEAMWORK_DOMAIN}/projects/api/v3/projects.json"
    params = {
        "projectCategoryIds": cat_id,
        "projectTagIds": TEAMWORK_ONBOARDING_TAG_ID,
        "status": "active",
        "pageSize": 200,
        "include": "tags",
    }
    try:
        r = requests.get(
            url, headers=_auth_header(), params=params, timeout=HTTP_TIMEOUT
        )
        r.raise_for_status()
        body = r.json()
    except requests.RequestException as exc:
        log.warning("Teamwork onboarding fail %s: %s", agency, exc)
        return None

    projects = body.get("projects", [])
    count = 0
    for p in projects:
        tag_ids = {t.get("id") for t in (p.get("tags") or [])}
        if TEAMWORK_ONBOARDING_TAG_ID in tag_ids:
            count += 1
    # If the API didn't echo tags inline, trust the server-side filter result.
    if count == 0 and projects:
        count = len(projects)
    return count
