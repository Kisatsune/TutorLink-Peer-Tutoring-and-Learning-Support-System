"""HTTP client for the TutorLink XML API.

Uses only the Python standard library:
  * urllib.request / urllib.parse  -> send requests (form-encoded data)
  * xml.etree.ElementTree          -> read the XML responses
"""
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

DEFAULT_BASE_URL = "http://127.0.0.1:8000/api/"


class ApiError(Exception):
    """Raised when the server cannot be reached or answers with an error."""


def _item(element):
    """<subject><id>1</id><name>Math</name></subject>  ->  {'id': '1', 'name': 'Math'}"""
    return {child.tag: (child.text or "") for child in element}


def _items(root):
    return [_item(element) for element in root]


class TutorLinkClient:
    def __init__(self, base_url=DEFAULT_BASE_URL):
        self.base_url = base_url.rstrip("/") + "/"
        self.token = None

    # Low-level request
    def _request(self, method, path, data=None, params=None):
        url = self.base_url + path.lstrip("/")
        if params:
            url += "?" + urllib.parse.urlencode(params)

        body = urllib.parse.urlencode(data).encode("utf-8") if data is not None else None
        request = urllib.request.Request(url, data=body, method=method)
        request.add_header("Accept", "application/xml")
        if body is not None:
            request.add_header("Content-Type", "application/x-www-form-urlencoded")
        if self.token:
            request.add_header("Authorization", "Token " + self.token)

        try:
            with urllib.request.urlopen(request, timeout=10) as response:
                raw = response.read()
        except urllib.error.HTTPError as error:  # server answered with 4xx / 5xx
            raise ApiError(self._error_text(error.read(), error.code)) from None
        except urllib.error.URLError as error:  # server unreachable
            raise ApiError(f"Cannot reach the server: {error.reason}") from None

        try:
            return ET.fromstring(raw)
        except ET.ParseError:
            raise ApiError("The server sent a response that is not valid XML.") from None

    @staticmethod
    def _error_text(raw, status):
        """Read <error>text</error> or <errors><error field='x'>text</error></errors>."""
        try:
            root = ET.fromstring(raw)
        except ET.ParseError:
            return f"Server error (HTTP {status})."
        if root.tag == "errors":
            lines = []
            for error in root:
                field = error.get("field")
                lines.append(f"{field}: {error.text}" if field else (error.text or ""))
            return "\n".join(lines)
        return root.text or f"Server error (HTTP {status})."

    # Authentication
    def login(self, username, password):
        root = self._request("POST", "login/", {"username": username, "password": password})
        self.token = root.findtext("token")
        return root.findtext("username")

    def logout(self):
        try:
            self._request("POST", "logout/", {})
        finally:
            self.token = None

    # Users and tutor approval
    def list_users(self, role=None, status=None):
        params = {}
        if role:
            params["role"] = role
        if status:
            params["status"] = status
        return _items(self._request("GET", "users/", params=params))

    def set_approval(self, user_id, approve):
        action = "approve" if approve else "reject"
        return self._request("POST", f"users/{user_id}/{action}/", {}).text

    # Subjects
    def list_subjects(self):
        return _items(self._request("GET", "subjects/"))

    def create_subject(self, data):
        return _item(self._request("POST", "subjects/", data))

    def update_subject(self, subject_id, data):
        return _item(self._request("PUT", f"subjects/{subject_id}/", data))

    def delete_subject(self, subject_id):
        return self._request("DELETE", f"subjects/{subject_id}/").text

    # Sessions
    def list_sessions(self):
        return _items(self._request("GET", "sessions/"))

    def create_session(self, data):
        return _item(self._request("POST", "sessions/", data))

    def update_session(self, session_id, data):
        return _item(self._request("PUT", f"sessions/{session_id}/", data))

    def delete_session(self, session_id):
        return self._request("DELETE", f"sessions/{session_id}/").text

    # Bookings and statistics
    def list_bookings(self):
        return _items(self._request("GET", "bookings/"))

    def stats(self):
        root = self._request("GET", "stats/")
        return {
            "totals": _item(root.find("totals")),
            "per_subject": _items(root.find("sessions_per_subject")),
            "top_tutors": _items(root.find("top_tutors")),
            "hours": _item(root.find("tutoring_hours")),
        }
