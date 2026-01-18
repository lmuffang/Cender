"""API client with Result pattern for consistent error handling."""

from dataclasses import dataclass
from typing import Any
import requests
import json


@dataclass
class Result:
    """Result type for API operations."""
    success: bool
    data: Any = None
    error: str | None = None


class APIClient:
    """API client for the Cender backend."""

    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")

    def _request(self, method: str, path: str, **kwargs) -> Result:
        """Make an HTTP request and return a Result."""
        try:
            response = requests.request(method, f"{self.base_url}{path}", **kwargs)
            if response.status_code in (200, 201):
                try:
                    return Result(success=True, data=response.json())
                except json.JSONDecodeError:
                    return Result(success=True, data=None)
            try:
                error_detail = response.json().get("detail", f"Request failed with status {response.status_code}")
            except json.JSONDecodeError:
                error_detail = f"Request failed with status {response.status_code}"
            return Result(success=False, error=error_detail)
        except requests.exceptions.ConnectionError:
            return Result(success=False, error="Cannot connect to backend server. Is it running?")
        except requests.exceptions.Timeout:
            return Result(success=False, error="Request timed out. Please try again.")
        except Exception as e:
            return Result(success=False, error=str(e))

    # User endpoints
    def list_users(self) -> Result:
        """List all users."""
        return self._request("GET", "/users/")

    def create_user(self, username: str, email: str) -> Result:
        """Create a new user."""
        return self._request("POST", "/users/", json={"username": username, "email": email})

    def get_user(self, user_id: int) -> Result:
        """Get a specific user."""
        return self._request("GET", f"/users/{user_id}")

    def delete_user(self, user_id: int) -> Result:
        """Delete a user and all associated data."""
        return self._request("DELETE", f"/users/{user_id}")

    # Gmail/Files endpoints
    def upload_credentials(self, user_id: int, file) -> Result:
        """Upload Gmail credentials."""
        return self._request("POST", f"/users/{user_id}/credentials", files={"file": file})

    def get_files_status(self, user_id: int) -> Result:
        """Check if credentials and resume are uploaded."""
        result = self._request("GET", f"/users/{user_id}/files-status")
        if not result.success:
            return Result(success=True, data={"has_credentials": False, "has_resume": False})
        return result

    def get_gmail_status(self, user_id: int) -> Result:
        """Check Gmail connection status."""
        result = self._request("GET", f"/users/{user_id}/gmail-status")
        if not result.success:
            return Result(
                success=True,
                data={
                    "connected": False,
                    "has_credentials": False,
                    "has_token": False,
                    "email": None,
                    "error": result.error or "Failed to check status"
                }
            )
        return result

    def get_gmail_auth_url(self, user_id: int) -> Result:
        """Get Gmail OAuth authorization URL."""
        return self._request("POST", f"/users/{user_id}/gmail-auth-url")

    def complete_gmail_auth(self, user_id: int, auth_code: str) -> Result:
        """Complete Gmail OAuth with authorization code."""
        return self._request("POST", f"/users/{user_id}/gmail-auth-complete", json={"auth_code": auth_code})

    def disconnect_gmail(self, user_id: int) -> Result:
        """Disconnect Gmail by removing the token."""
        return self._request("POST", f"/users/{user_id}/gmail-disconnect")

    def upload_resume(self, user_id: int, file) -> Result:
        """Upload resume PDF."""
        return self._request("POST", f"/users/{user_id}/resume", files={"file": file})

    # Template endpoints
    def get_template(self, user_id: int) -> Result:
        """Load user's template."""
        result = self._request("GET", f"/users/{user_id}/template")
        if not result.success:
            return Result(success=True, data={"content": "", "subject": ""})
        return result

    def save_template(self, user_id: int, content: str, subject: str) -> Result:
        """Save user's template."""
        return self._request("POST", f"/users/{user_id}/template", json={"content": content, "subject": subject})

    # Recipient endpoints
    def list_recipients(self, user_id: int, used: bool | None = None) -> Result:
        """List recipients for a user."""
        params = {}
        if used is not None:
            params["used"] = str(used).lower()
        result = self._request("GET", f"/users/{user_id}/recipients", params=params)
        if not result.success:
            return Result(success=True, data=[])
        return result

    def import_recipients_csv(self, user_id: int, file) -> Result:
        """Parse CSV and extract recipients."""
        return self._request("POST", f"/users/{user_id}/recipients-csv", files={"file": file})

    def delete_all_recipients(self, user_id: int) -> Result:
        """Delete all recipients for a user."""
        return self._request("DELETE", f"/users/{user_id}/recipients")

    # Email endpoints
    def get_email_preview(self, user_id: int, recipient_id: int, subject: str) -> Result:
        """Get email preview from backend."""
        return self._request(
            "POST",
            f"/users/{user_id}/preview-email/{recipient_id}",
            data={"subject": subject},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )

    def send_emails_stream(self, user_id: int, recipient_ids: list[int], subject: str, dry_run: bool = False):
        """Send emails stream - yields events."""
        payload = {"recipient_ids": recipient_ids, "subject": subject, "dry_run": dry_run}
        try:
            with requests.post(
                f"{self.base_url}/users/{user_id}/send-emails/stream",
                json=payload,
                stream=True
            ) as response:
                if response.status_code != 200:
                    try:
                        error_msg = response.json().get("detail", "Failed to start email sending")
                    except Exception:
                        error_msg = f"Server error (status {response.status_code})"
                    yield {"error": error_msg}
                    return

                for line in response.iter_lines():
                    if not line:
                        continue
                    try:
                        event = json.loads(line.decode("utf-8"))
                        yield event
                        if "error" in event:
                            return
                    except json.JSONDecodeError:
                        continue
        except requests.exceptions.ConnectionError:
            yield {"error": "Cannot connect to backend server. Is it running?"}
        except requests.exceptions.Timeout:
            yield {"error": "Request timed out. Please try again."}
        except Exception as e:
            yield {"error": f"Unexpected error: {str(e)}"}

    def get_user_stats(self, user_id: int) -> Result:
        """Get user statistics."""
        result = self._request("GET", f"/users/{user_id}/stats")
        if not result.success:
            return Result(
                success=True,
                data={"total_sent": 0, "total_failed": 0, "total_skipped": 0, "total_emails": 0}
            )
        return result

    def get_email_logs(self, user_id: int, limit: int = 100) -> Result:
        """Get email logs for a user."""
        result = self._request("GET", f"/users/{user_id}/email-logs", params={"limit": limit})
        if not result.success:
            return Result(success=True, data=[])
        return result

    def delete_email_logs(
        self,
        user_id: int,
        recipient_id: int | None = None,
        status: str | None = None,
        before_date: str | None = None,
        all_logs: bool = False
    ) -> Result:
        """Delete email logs for a user."""
        params = {}
        if all_logs:
            params["all"] = "true"
        if recipient_id:
            params["recipient_id"] = str(recipient_id)
        if status:
            params["status"] = str(status)
        if before_date:
            if hasattr(before_date, "strftime"):
                params["before_date"] = before_date.strftime("%Y-%m-%d")
            else:
                params["before_date"] = str(before_date)
        return self._request("DELETE", f"/users/{user_id}/email-logs", params=params)

    def delete_email_log(self, user_id: int, log_id: int) -> Result:
        """Delete a specific email log."""
        return self._request("DELETE", f"/users/{user_id}/email-logs/{log_id}")
