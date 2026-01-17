import streamlit as st
import requests
import pandas as pd
import json
import os

# Configuration
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")

st.set_page_config(page_title="Cender", page_icon="📧", layout="wide")

# Initialize session state
if "current_user" not in st.session_state:
    st.session_state.current_user = None
if "user_created" not in st.session_state:
    st.session_state.user_created = False
if "creds_upload_key" not in st.session_state:
    st.session_state.creds_upload_key = 0
if "resume_upload_key" not in st.session_state:
    st.session_state.resume_upload_key = 0
if "csv_upload_key" not in st.session_state:
    st.session_state.csv_upload_key = 0
if "sending_emails" not in st.session_state:
    st.session_state.sending_emails = False
if "send_results" not in st.session_state:
    st.session_state.send_results = None
if "send_data" not in st.session_state:
    st.session_state.send_data = None


def load_users():
    """Load list of users from backend"""
    try:
        response = requests.get(f"{BACKEND_URL}/users/")
        if response.status_code == 200:
            return response.json()
    except Exception as e:
        st.error(f"Error loading users: {e}")
    return []


def create_user(username, email):
    """Create a new user"""
    try:
        response = requests.post(
            f"{BACKEND_URL}/users/", json={"username": username, "email": email}
        )
        if response.status_code == 200:
            return True, None
        else:
            return False, response.json().get("detail", "Failed to create user")
    except Exception as e:
        return False, str(e)


def delete_user(user_id):
    """Delete a user and all associated data"""
    try:
        response = requests.delete(f"{BACKEND_URL}/users/{user_id}")
        if response.status_code == 200:
            return True, response.json()
        else:
            return False, response.json().get("detail", "Failed to delete user")
    except Exception as e:
        return False, str(e)


def upload_credentials(user_id, file):
    """Upload Gmail credentials"""
    try:
        files = {"file": file}
        response = requests.post(f"{BACKEND_URL}/users/{user_id}/credentials", files=files)
        return response.status_code == 200
    except:
        return False


def get_gmail_status(user_id):
    """Check Gmail connection status"""
    try:
        response = requests.get(f"{BACKEND_URL}/users/{user_id}/gmail-status")
        if response.status_code == 200:
            return response.json()
    except:
        pass
    return {"connected": False, "has_credentials": False, "has_token": False, "email": None, "error": "Failed to check status"}


def get_gmail_auth_url(user_id):
    """Get Gmail OAuth authorization URL"""
    try:
        response = requests.post(f"{BACKEND_URL}/users/{user_id}/gmail-auth-url")
        if response.status_code == 200:
            return response.json().get("auth_url"), None
        else:
            return None, response.json().get("detail", "Failed to get auth URL")
    except Exception as e:
        return None, str(e)


def complete_gmail_auth(user_id, auth_code):
    """Complete Gmail OAuth with authorization code"""
    try:
        response = requests.post(
            f"{BACKEND_URL}/users/{user_id}/gmail-auth-complete",
            json={"auth_code": auth_code}
        )
        if response.status_code == 200:
            return True, response.json().get("message", "Connected!")
        else:
            return False, response.json().get("detail", "Authorization failed")
    except Exception as e:
        return False, str(e)


def disconnect_gmail(user_id):
    """Disconnect Gmail by removing the token"""
    try:
        response = requests.post(f"{BACKEND_URL}/users/{user_id}/gmail-disconnect")
        if response.status_code == 200:
            return True, response.json().get("message", "Disconnected!")
        else:
            return False, response.json().get("detail", "Disconnect failed")
    except Exception as e:
        return False, str(e)


def get_files_status(user_id):
    """Check if credentials and resume are uploaded"""
    try:
        response = requests.get(f"{BACKEND_URL}/users/{user_id}/files-status")
        if response.status_code == 200:
            return response.json()
    except:
        pass
    return {"has_credentials": False, "has_resume": False}


def upload_resume(user_id, file):
    """Upload resume PDF"""
    try:
        files = {"file": file}
        response = requests.post(f"{BACKEND_URL}/users/{user_id}/resume", files=files)
        return response.status_code == 200
    except:
        return False


def load_template(user_id):
    """Load user's template"""
    try:
        response = requests.get(f"{BACKEND_URL}/users/{user_id}/template")
        if response.status_code == 200:
            return response.json()
    except:
        pass
    return ""


def save_template(user_id, content, subject=""):
    """Save user's template"""
    try:
        response = requests.post(
            f"{BACKEND_URL}/users/{user_id}/template", json={"content": content, "subject": subject}
        )
        return response.status_code in [200, 201]
    except:
        return False


def upload_recipients_csv(user_id, file):
    """Parse CSV and extract recipients"""
    try:
        files = {"file": file}
        response = requests.post(f"{BACKEND_URL}/users/{user_id}/recipients-csv", files=files)
        if response.status_code == 200:
            response_payload = response.json()
            return True, response_payload
        else:
            return False, response.json().get("detail", "Failed to import CSV")
    except Exception as e:
        return False, str(e)


def fetch_recipients(user_id: int, used: bool | None = None):
    """Fetch recipients for a user"""
    try:
        params = {}
        if used is not None:
            params["used"] = str(used).lower()

        resp = requests.get(
            f"{BACKEND_URL}/users/{user_id}/recipients",
            params=params,
        )
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        st.error(f"Error fetching recipients: {e}")
        return []


def get_email_preview(user_id: int, recipient_id: int, subject: str) -> dict:
    """Get email preview from backend"""
    try:
        resp = requests.post(
            f"{BACKEND_URL}/users/{user_id}/preview-email/{recipient_id}",
            data={"subject": subject},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        st.error(f"Error getting preview: {e}")
        return None


def send_emails_stream(user_id, recipient_ids, subject, dry_run=False):
    """Send emails stream"""
    try:
        payload = {"recipient_ids": recipient_ids, "subject": subject, "dry_run": dry_run}

        with requests.post(
            f"{BACKEND_URL}/users/{user_id}/send-emails/stream", json=payload, stream=True
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
                    # Stop on stream error
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


def get_user_stats(user_id):
    """Get user statistics"""
    try:
        response = requests.get(f"{BACKEND_URL}/users/{user_id}/stats")
        if response.status_code == 200:
            return response.json()
    except:
        pass
    return {"total_sent": 0, "total_failed": 0, "total_skipped": 0, "total_emails": 0}


def get_email_logs(user_id, limit=100):
    """Get email logs for a user"""
    try:
        response = requests.get(
            f"{BACKEND_URL}/users/{user_id}/email-logs", params={"limit": limit}
        )
        if response.status_code == 200:
            return response.json()
    except:
        pass
    return []


def delete_email_logs(user_id, recipient_id=None, status=None, before_date=None, all_logs=False):
    """Delete email logs for a user"""
    try:
        params = {}
        if all_logs:
            params["all"] = "true"
        if recipient_id:
            params["recipient_id"] = str(recipient_id)
        if status:
            params["status"] = str(status)  # Convert to string for query param
        if before_date:
            if hasattr(before_date, "strftime"):
                params["before_date"] = before_date.strftime("%Y-%m-%d")
            else:
                params["before_date"] = str(before_date)

        response = requests.delete(f"{BACKEND_URL}/users/{user_id}/email-logs", params=params)
        if response.status_code == 200:
            return True, response.json()
        else:
            return False, response.json().get("detail", "Failed to delete logs")
    except Exception as e:
        return False, str(e)


def delete_email_log(user_id, log_id):
    """Delete a specific email log"""
    try:
        response = requests.delete(f"{BACKEND_URL}/users/{user_id}/email-logs/{log_id}")
        return response.status_code == 200
    except:
        return False


def delete_all_recipients(user_id):
    """Delete all recipients for a user"""
    try:
        response = requests.delete(f"{BACKEND_URL}/users/{user_id}/recipients")
        if response.status_code == 200:
            return True, response.json()
        else:
            return False, response.json().get("detail", "Failed to delete recipients")
    except Exception as e:
        return False, str(e)


# Main UI
st.title("📧 Cender")

# Sidebar - User Selection
with st.sidebar:
    st.header("👤 User Selection")

    users = load_users()

    if users:
        user_options = {f"{u['username']} ({u['email']})": u for u in users}
        option_keys = list(user_options.keys())

        # Determine current index based on session state
        current_index = 0
        if st.session_state.current_user:
            current_key = f"{st.session_state.current_user['username']} ({st.session_state.current_user['email']})"
            if current_key in option_keys:
                current_index = option_keys.index(current_key)

        selected = st.selectbox(
            "Select User",
            options=option_keys,
            index=current_index,
            key="user_select"
        )

        # Update current_user based on selection
        if selected:
            new_user = user_options[selected]
            # Initialize if no user selected yet
            if st.session_state.current_user is None:
                st.session_state.current_user = new_user
            # Handle user switch
            elif st.session_state.current_user["id"] != new_user["id"]:
                st.session_state.current_user = new_user
                # Clear any pending operations when switching users
                st.session_state.send_results = None
                st.session_state.sending_emails = False
                st.session_state.send_data = None
                if "gmail_auth_url" in st.session_state:
                    del st.session_state["gmail_auth_url"]
                st.rerun()

    st.divider()

    # Create new user
    with st.expander("➕ Create New User"):
        new_username = st.text_input("Username", key="new_username")
        new_email = st.text_input("Email", key="new_email")
        if st.button("Create User"):
            if new_username and new_email:
                success, message = create_user(new_username, new_email)
                if success:
                    st.session_state.user_created = True
                    st.success("User created! Refreshing...")
                    st.rerun()
                else:
                    st.error(f"Failed to create user: {message}")
            else:
                st.error("Please fill all fields")

    # Show success message if user was just created
    if st.session_state.user_created:
        st.success("User created successfully!")
        st.session_state.user_created = False

    # User stats
    if st.session_state.current_user:
        st.divider()
        st.subheader("📊 Statistics")
        stats = get_user_stats(st.session_state.current_user["id"])
        col1, col2 = st.columns(2)
        col1.metric("Sent", stats["total_sent"])
        col2.metric("Failed", stats["total_failed"])

        # Delete user section
        st.divider()
        with st.expander("🗑️ Delete User", expanded=False):
            st.warning(
                f"**This will permanently delete:**\n"
                f"- User '{st.session_state.current_user['username']}'\n"
                f"- All email logs ({stats['total_sent'] + stats['total_failed']} records)\n"
                f"- Email template\n"
                f"- Uploaded files (credentials, token, resume)"
            )
            st.info("Recipients are shared and will NOT be deleted.")

            confirm_text = st.text_input(
                f"Type **{st.session_state.current_user['username']}** to confirm:",
                key="delete_user_confirm"
            )

            if st.button("🗑️ Delete User Permanently", type="primary", use_container_width=True):
                if confirm_text == st.session_state.current_user["username"]:
                    success, result = delete_user(st.session_state.current_user["id"])
                    if success:
                        st.success(result.get("message", "User deleted successfully!"))
                        st.session_state.current_user = None
                        st.rerun()
                    else:
                        st.error(f"Failed to delete user: {result}")
                else:
                    st.error("Username doesn't match. Please type the exact username to confirm.")


# Main content
if not st.session_state.current_user:
    st.info("👈 Please select or create a user to get started")
    st.stop()

user_id = st.session_state.current_user["id"]
username = st.session_state.current_user["username"]

# Block UI while sending emails
if st.session_state.sending_emails:
    st.warning("📧 **Sending emails in progress...**")
    st.info("Please wait until all emails are sent. Do not close this page.")

    # Show progress container
    progress_container = st.container()

    # Process the email sending
    send_data = st.session_state.get("send_data", {})
    recipient_ids = send_data.get("recipient_ids", [])
    subject = send_data.get("subject", "")
    dry_run = send_data.get("dry_run", False)

    with progress_container:
        status_box = st.empty()
        progress = st.progress(0)
        log_box = st.container()
        sent = 0
        failed = 0
        skipped = 0
        total = len(recipient_ids)
        errors = []
        stream_error = None

        for i, event in enumerate(
            send_emails_stream(user_id, recipient_ids, subject, dry_run)
        ):
            if "error" in event:
                stream_error = event["error"]
                break

            # Update UI incrementally
            with log_box:
                status_text = (
                    f"{event.get('email', 'N/A')} → {event.get('status', 'unknown')}"
                )
                if event.get("message"):
                    status_text += f" ({event.get('message')})"
                st.text(status_text)

            status_box.info(
                f"Last email: {event.get('email', 'N/A')} → {event.get('status', 'unknown')}"
            )

            status = event.get("status", "")
            if status == "sent":
                sent += 1
            elif status == "failed":
                failed += 1
                errors.append(
                    {
                        "email": event.get("email", "N/A"),
                        "message": event.get("message", "Unknown error"),
                    }
                )
            elif status == "skipped":
                skipped += 1

            if total > 0:
                progress.progress((i + 1) / total)

    # Store results and clear sending state
    st.session_state.send_results = {
        "sent": sent,
        "failed": failed,
        "skipped": skipped,
        "errors": errors,
        "stream_error": stream_error,
        "dry_run": dry_run,
    }
    st.session_state.sending_emails = False
    st.session_state.send_data = None
    st.rerun()

    # This won't be reached due to rerun, but just in case
    st.stop()

# Show results from previous send operation
if st.session_state.send_results:
    results = st.session_state.send_results
    st.divider()

    if results["stream_error"]:
        st.error(f"Error: {results['stream_error']}")
    else:
        col1, col2, col3 = st.columns(3)
        col1.metric("✅ Sent", results["sent"])
        col2.metric("❌ Failed", results["failed"])
        col3.metric("⏭️ Skipped", results["skipped"])

        if results["errors"]:
            with st.expander("Failed emails details"):
                for err in results["errors"]:
                    st.write(f"- {err['email']}: {err['message']}")

        if results["dry_run"]:
            st.info("Dry run completed - no emails were actually sent")
        else:
            st.success("Email sending completed!")

    if st.button("Dismiss Results"):
        st.session_state.send_results = None
        st.rerun()

    st.divider()

st.subheader(f"Welcome, {username}! 👋")

# Tabs
tab1, tab2, tab3 = st.tabs(["📤 Send Emails", "⚙️ Configuration", "📜 History"])

with tab1:
    st.header("Send Emails")

    template = load_template(user_id)
    template_content = template.get("content", "") if template else ""
    subject = template.get("subject", "") if template else ""
    # Email subject
    subject = st.text_input(
        "Email Subject", placeholder="Candidature spontanée", value=subject, key="email_subject"
    )

    # Template editor
    st.subheader("Email Template")
    template_content = st.text_area(
        "Template (use {salutation} and {company} as placeholders)",
        value=template_content,
        height=200,
        key="template_content",
    )

    col_save, col_info = st.columns([1, 3])
    with col_save:
        if st.button("💾 Save Template"):
            if save_template(user_id, template_content, subject):
                st.success("Template saved!")
            else:
                st.error("Failed to save template")
    with col_info:
        st.caption("💡 Save your template before sending emails")

    st.divider()

    # CSV Upload
    st.subheader("Upload Recipients CSV")
    st.info(
        "CSV should have columns: Email, First Name, Last Name, Company (or Company Name for Emails)"
    )

    csv_file = st.file_uploader(
        "Choose CSV file", type=["csv"],
        key=f"csv_{st.session_state.csv_upload_key}"
    )

    if csv_file and st.button("📥 Import CSV"):
        success, result = upload_recipients_csv(user_id, csv_file)
        if success:
            st.success(
                f"Added {result.get('created', 0)} new recipients! ({result.get('total', 0)} processed in total)"
            )
            st.session_state.csv_upload_key += 1
            st.rerun()
        else:
            st.error(f"Error importing CSV: {result}")

    # Display recipients
    filter_option = st.radio(
        "Filter recipients",
        options=["All", "Used", "Unused"],
        horizontal=True,
        key="recipient_filter",
    )

    used_filter = {
        "All": None,
        "Used": True,
        "Unused": False,
    }[filter_option]

    displayed_recipients = fetch_recipients(user_id, used_filter)

    st.subheader(f"Recipients ({len(displayed_recipients)})")

    if not displayed_recipients:
        st.info("No recipients found. Upload a CSV file to import recipients.")
    else:
        # Display recipients with selection
        df = pd.DataFrame(displayed_recipients)

        # Add selection column
        if "selected_recipients" not in st.session_state:
            st.session_state.selected_recipients = []

        # Multi-select recipients
        selected_indices = st.multiselect(
            "Select recipients to send emails to (leave empty to send to all unused)",
            options=range(len(displayed_recipients)),
            format_func=lambda i: f"{displayed_recipients[i].get('email', 'N/A')} - {displayed_recipients[i].get('first_name', '')} {displayed_recipients[i].get('last_name', '')}",
            key="recipient_selection",
        )

        st.dataframe(df[["email", "first_name", "last_name", "company"]], use_container_width=True)

        # Preview
        if displayed_recipients:
            st.subheader("📝 Email Preview")
            preview_idx = st.selectbox(
                "Select recipient for preview",
                options=range(len(displayed_recipients)),
                format_func=lambda i: displayed_recipients[i].get("email", "N/A"),
                key="preview_recipient",
            )

            if preview_idx is not None and subject:
                recipient = displayed_recipients[preview_idx]
                recipient_id = recipient.get("id")

                if recipient_id:
                    preview = get_email_preview(user_id, recipient_id, subject)
                    if preview:
                        st.text_area(
                            "Preview",
                            value=preview.get("body", ""),
                            height=200,
                            disabled=True,
                            key="preview_body",
                        )
                    else:
                        st.warning("Could not generate preview. Make sure template is saved.")
                else:
                    st.warning("Recipient ID not found")
            elif not subject:
                st.info("Enter a subject to see preview")

        st.divider()

        dry_run = st.checkbox("🧪 Dry Run (Don't actually send)", value=False, key="dry_run")

        st.divider()

        if st.button("📧 Send Emails", type="primary", use_container_width=True):
            # Validation checks
            if not subject:
                st.error("Please enter an email subject")
                st.stop()
            if not template_content:
                st.error("Please enter an email template")
                st.stop()

            # Pre-flight checks (skip for dry run)
            if not dry_run:
                preflight_status = get_files_status(user_id)
                gmail_preflight = get_gmail_status(user_id)

                if not preflight_status["has_credentials"]:
                    st.error("Gmail credentials not uploaded. Please go to Configuration tab and upload your credentials.json file.")
                    st.stop()
                if not gmail_preflight["connected"]:
                    error_detail = gmail_preflight.get("error", "Unknown error")
                    st.error(f"Gmail not connected. Please go to Configuration tab to connect your Gmail account. ({error_detail})")
                    st.stop()
                if not preflight_status["has_resume"]:
                    st.error("Resume not uploaded. Please go to Configuration tab and upload your resume PDF.")
                    st.stop()

            # Save template first
            if not save_template(user_id, template_content, subject):
                st.error("Failed to save template. Please try again.")
                st.stop()

            # Determine which recipients to send to
            if selected_indices:
                recipient_ids = [displayed_recipients[i]["id"] for i in selected_indices]
            else:
                # Send to all unused recipients
                unused_recipients = fetch_recipients(user_id, used=False)
                recipient_ids = [r["id"] for r in unused_recipients]

            if not recipient_ids:
                st.warning("No recipients selected or no unused recipients available.")
                st.stop()

            # Set sending state and trigger rerun to block UI
            st.session_state.sending_emails = True
            st.session_state.send_data = {
                "recipient_ids": recipient_ids,
                "subject": subject,
                "dry_run": dry_run,
            }
            st.rerun()

with tab2:
    st.header("Configuration")

    # Get status information
    gmail_status = get_gmail_status(user_id)
    files_status = get_files_status(user_id)

    # Setup Status Overview
    st.subheader("Setup Status")
    col1, col2, col3 = st.columns(3)

    with col1:
        if files_status["has_credentials"]:
            st.success("Credentials: Uploaded")
        else:
            st.error("Credentials: Missing")

    with col2:
        if gmail_status["connected"]:
            st.success(f"Gmail: Connected")
        elif gmail_status["has_credentials"]:
            st.warning("Gmail: Not authorized")
        else:
            st.error("Gmail: Not connected")

    with col3:
        if files_status["has_resume"]:
            st.success("Resume: Uploaded")
        else:
            st.error("Resume: Missing")

    st.divider()

    # Credentials Upload Section
    st.subheader("1. Upload Gmail Credentials")
    if files_status["has_credentials"]:
        st.success("Credentials file already uploaded. Upload again to replace.")
    else:
        st.info("Upload your OAuth 2.0 credentials JSON file from Google Cloud Console")

    credentials_file = st.file_uploader(
        "Choose credentials file", type=["json"],
        key=f"creds_{st.session_state.creds_upload_key}"
    )

    if credentials_file:
        if st.button("Upload Credentials"):
            if upload_credentials(user_id, credentials_file):
                st.success("Credentials uploaded successfully!")
                st.session_state.creds_upload_key += 1
                st.rerun()
            else:
                st.error("Failed to upload credentials")

    st.divider()

    # OAuth Authorization Section
    st.subheader("2. Connect to Gmail")
    if not files_status["has_credentials"]:
        st.info("Please upload credentials first")
    elif gmail_status["connected"]:
        st.success("Already connected!")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Reconnect", help="Use this if you need to re-authorize"):
                auth_url, error = get_gmail_auth_url(user_id)
                if auth_url:
                    st.session_state["gmail_auth_url"] = auth_url
                else:
                    st.error(f"Failed to get authorization URL: {error}")
        with col2:
            if st.button("Disconnect", help="Remove Gmail connection"):
                success, message = disconnect_gmail(user_id)
                if success:
                    st.success(message)
                    st.rerun()
                else:
                    st.error(message)
    else:
        if st.button("Connect to Gmail"):
            auth_url, error = get_gmail_auth_url(user_id)
            if auth_url:
                st.session_state["gmail_auth_url"] = auth_url
            else:
                st.error(f"Failed to get authorization URL: {error}")

    # Show authorization flow if URL is available
    if "gmail_auth_url" in st.session_state:
        st.markdown("---")
        st.markdown("**Step 1:** Open this URL in your browser:")
        st.code(st.session_state["gmail_auth_url"], language=None)

        st.markdown("**Step 2:** Sign in and authorize the application")

        st.markdown("**Step 3:** After authorizing, you'll be redirected to a page that shows an error "
                   "(this is expected). **Copy the entire URL** from your browser's address bar.")
        st.info("The URL will look like:\n\n"
               "`http://localhost/?state=...&code=4/0ABC...&scope=...`\n\n"
               "Just copy the **entire URL** - we'll extract the code automatically!")

        st.markdown("**Step 4:** Paste the full redirect URL below:")
        auth_code = st.text_input("Redirect URL", key="gmail_auth_code",
                                  placeholder="http://localhost/?state=...&code=...&scope=...")

        col1, col2 = st.columns(2)
        with col1:
            if st.button("Connect Gmail", type="primary"):
                if auth_code:
                    success, message = complete_gmail_auth(user_id, auth_code)
                    if success:
                        st.success(message)
                        del st.session_state["gmail_auth_url"]
                        if "gmail_auth_code" in st.session_state:
                            del st.session_state["gmail_auth_code"]
                        st.rerun()
                    else:
                        st.error(message)
                else:
                    st.warning("Please paste the redirect URL")
        with col2:
            if st.button("Cancel"):
                del st.session_state["gmail_auth_url"]
                st.rerun()

    st.divider()

    # Resume Upload Section
    st.subheader("3. Upload Resume")
    if files_status["has_resume"]:
        st.success("Resume already uploaded. Upload again to replace.")
    else:
        st.info("Upload your resume PDF file")

    resume_file = st.file_uploader(
        "Choose resume PDF", type=["pdf"],
        key=f"resume_{st.session_state.resume_upload_key}"
    )

    if resume_file:
        if st.button("Upload Resume"):
            if upload_resume(user_id, resume_file):
                st.success("Resume uploaded successfully!")
                st.session_state.resume_upload_key += 1
                st.rerun()
            else:
                st.error("Failed to upload resume")

    st.divider()

    # Delete Recipients Section
    st.subheader("4. Manage Recipients")
    recipients_count = len(fetch_recipients(user_id))
    st.info(f"You have **{recipients_count}** recipients linked to your account.")

    with st.expander("Remove All Recipients", expanded=False):
        st.warning(
            "This will remove all recipients from your account. "
            "The recipients themselves are not deleted (they may be used by other users)."
        )

        confirm_delete = st.checkbox(
            "I understand this will remove all my recipients",
            key="confirm_delete_recipients"
        )

        if st.button("Remove All Recipients", type="primary", disabled=not confirm_delete):
            success, result = delete_all_recipients(user_id)
            if success:
                st.success(f"Removed {result.get('count', 0)} recipients from your account.")
                st.rerun()
            else:
                st.error(f"Failed to remove recipients: {result}")

with tab3:
    st.header("Email History")

    stats = get_user_stats(user_id)
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Sent", stats["total_sent"])
    col2.metric("Total Failed", stats["total_failed"])
    col3.metric("Total Skipped", stats["total_skipped"])
    col4.metric("Total Emails", stats["total_emails"])

    st.divider()

    # Reset/Delete email logs section
    with st.expander("🔄 Reset Sent Emails", expanded=False):
        st.warning("⚠️ Resetting sent emails will allow you to re-send emails to those recipients.")
        st.info("💡 This deletes the email logs. You can filter by recipient, status, or date.")

        col1, col2 = st.columns(2)

        with col1:
            reset_option = st.radio(
                "Reset options",
                options=["All sent emails", "By recipient", "By status", "Before date"],
                key="reset_option",
            )

        with col2:
            if reset_option == "By recipient":
                recipients = fetch_recipients(user_id)
                recipient_options = {f"{r.get('email', 'N/A')}": r["id"] for r in recipients}
                selected_recipient = st.selectbox(
                    "Select recipient",
                    options=list(recipient_options.keys()),
                    key="reset_recipient",
                )
                reset_recipient_id = (
                    recipient_options[selected_recipient] if selected_recipient else None
                )
            elif reset_option == "By status":
                reset_status = st.selectbox(
                    "Select status", options=["sent", "failed", "skipped"], key="reset_status"
                )
            elif reset_option == "Before date":
                reset_date = st.date_input("Delete logs before this date", key="reset_date")

        if st.button("🗑️ Delete Email Logs", type="primary"):
            try:
                if reset_option == "All sent emails":
                    success, result = delete_email_logs(user_id, status="sent")
                elif reset_option == "By recipient":
                    if not selected_recipient:
                        st.error("Please select a recipient")
                        st.stop()
                    success, result = delete_email_logs(user_id, recipient_id=reset_recipient_id)
                elif reset_option == "By status":
                    success, result = delete_email_logs(user_id, status=reset_status)
                elif reset_option == "Before date":
                    success, result = delete_email_logs(user_id, before_date=reset_date)
                else:
                    success, result = False, "Invalid option"
            except Exception as e:
                success, result = False, str(e)

            if success:
                st.success(f"✅ {result.get('message', 'Email logs deleted successfully')}")
                st.rerun()
            else:
                st.error(f"❌ Failed to delete logs: {result}")

    st.divider()

    # Email logs
    limit = st.slider("Number of logs to display", min_value=10, max_value=500, value=100, step=10)
    logs = get_email_logs(user_id, limit)

    if logs:
        logs_df = pd.DataFrame(logs)
        # Format datetime
        if "sent_at" in logs_df.columns:
            logs_df["sent_at"] = pd.to_datetime(logs_df["sent_at"]).dt.strftime("%Y-%m-%d %H:%M:%S")

        # Display logs table
        st.dataframe(
            logs_df[["id", "recipient_email", "subject", "status", "sent_at", "error_message"]],
            use_container_width=True,
            column_config={
                "recipient_email": "Email",
            }
        )

        # Delete individual log
        st.subheader("Delete Individual Log")
        log_ids = [log["id"] for log in logs]
        selected_log_id = st.selectbox(
            "Select log to delete",
            options=log_ids,
            format_func=lambda x: f"Log #{x}",
            key="delete_log_select",
        )

        if st.button("🗑️ Delete Selected Log", key="delete_single_log"):
            if delete_email_log(user_id, selected_log_id):
                st.success("✅ Email log deleted successfully!")
                st.rerun()
            else:
                st.error("❌ Failed to delete email log")
    else:
        st.info("No email logs found")

# Footer
st.divider()
st.caption("Cender - The resume sender made with Streamlit & FastAPI")
