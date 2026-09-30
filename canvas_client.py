import os

import requests

TIMEOUT_SECONDS = 15


class CanvasAuthError(Exception):
    """The user's Canvas PAT is missing, unreadable, or was rejected by Canvas."""


class CanvasClient:
    """Thin wrapper around the few Canvas REST endpoints this app needs."""

    def __init__(self, pat):
        self._base_url = os.environ["CANVAS_BASE_URL"].rstrip("/")
        self._headers = {"Authorization": f"Bearer {pat}"}

    def _get(self, url, params=None):
        response = requests.get(
            url, headers=self._headers, params=params, timeout=TIMEOUT_SECONDS
        )
        if response.status_code == 401:
            raise CanvasAuthError()
        response.raise_for_status()
        return response

    def _get_all(self, path, params):
        """Fetches every page of a list endpoint by following the Link header."""
        response = self._get(self._base_url + path, {**params, "per_page": 100})
        items = response.json()
        while "next" in response.links:
            # The "next" URL already carries the query parameters.
            response = self._get(response.links["next"]["url"])
            items.extend(response.json())
        return items

    def get_self(self):
        return self._get(self._base_url + "/api/v1/users/self").json()

    def get_active_courses(self):
        courses = self._get_all(
            "/api/v1/courses", {"enrollment_state": "active", "include[]": "term"}
        )
        # Courses outside their access dates come back with no name; skip them.
        return [c for c in courses if not c.get("access_restricted_by_date")]

    def get_assignments(self, canvas_course_id):
        return self._get_all(f"/api/v1/courses/{canvas_course_id}/assignments", {})
