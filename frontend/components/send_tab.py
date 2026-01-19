"""Send emails tab component."""

import streamlit as st
import pandas as pd
from api.client import APIClient


def render(api: APIClient, user_id: int):
    """Render the send emails tab."""
    st.header("Send Emails")

    result = api.get_template(user_id)
    template = result.data
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
            result = api.save_template(user_id, template_content, subject)
            if result.success:
                st.success("Template saved!")
            else:
                st.error(f"Failed to save template: {result.error}")
    with col_info:
        st.caption("💡 Save your template before sending emails")

    st.divider()

    # CSV Upload
    _render_csv_upload(api, user_id)

    # Display recipients
    _render_recipients(api, user_id, template_content, subject)


def _render_csv_upload(api: APIClient, user_id: int):
    """Render CSV upload section."""
    st.subheader("Upload Recipients CSV")
    st.info(
        "CSV should have columns: Email, First Name, Last Name, Company (or Company Name for Emails)"
    )

    csv_file = st.file_uploader(
        "Choose CSV file", type=["csv"],
        key=f"csv_{st.session_state.csv_upload_key}"
    )

    if csv_file and st.button("📥 Import CSV"):
        result = api.import_recipients_csv(user_id, csv_file)
        if result.success:
            st.success(
                f"Added {result.data.get('created', 0)} new recipients! ({result.data.get('total', 0)} processed in total)"
            )
            st.session_state.csv_upload_key += 1
            st.rerun()
        else:
            st.error(f"Error importing CSV: {result.error}")


def _render_recipients(api: APIClient, user_id: int, template_content: str, subject: str):
    """Render recipients list and send functionality."""
    # Filter recipients
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

    result = api.list_recipients(user_id, used_filter)
    displayed_recipients = result.data if result.success else []

    st.subheader(f"Recipients ({len(displayed_recipients)})")

    if not displayed_recipients:
        st.info("No recipients found. Upload a CSV file to import recipients.")
        return

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
    _render_preview(api, user_id, displayed_recipients, subject)

    st.divider()

    dry_run = st.checkbox("🧪 Dry Run (Don't actually send)", value=False, key="dry_run")

    st.divider()

    # Send button
    _render_send_button(api, user_id, displayed_recipients, selected_indices, subject, template_content, dry_run)


def _render_preview(api: APIClient, user_id: int, displayed_recipients: list, subject: str):
    """Render email preview section."""
    if not displayed_recipients:
        return

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
            result = api.get_email_preview(user_id, recipient_id, subject)
            if result.success and result.data:
                st.text_area(
                    "Preview",
                    value=result.data.get("body", ""),
                    height=200,
                    disabled=True,
                    key="preview_body",
                )
                attachment = result.data.get("attachment_filename")
                if attachment:
                    st.caption(f"📎 Attachment: {attachment}")
                else:
                    st.caption("⚠️ No resume attached")
            else:
                st.warning("Could not generate preview. Make sure template is saved.")
        else:
            st.warning("Recipient ID not found")
    elif not subject:
        st.info("Enter a subject to see preview")


def _render_send_button(
    api: APIClient,
    user_id: int,
    displayed_recipients: list,
    selected_indices: list,
    subject: str,
    template_content: str,
    dry_run: bool
):
    """Render the send emails button with validation."""
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
            files_result = api.get_files_status(user_id)
            preflight_status = files_result.data

            gmail_result = api.get_gmail_status(user_id)
            gmail_preflight = gmail_result.data

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
        save_result = api.save_template(user_id, template_content, subject)
        if not save_result.success:
            st.error("Failed to save template. Please try again.")
            st.stop()

        # Determine which recipients to send to
        if selected_indices:
            recipient_ids = [displayed_recipients[i]["id"] for i in selected_indices]
        else:
            # Send to all unused recipients
            unused_result = api.list_recipients(user_id, used=False)
            unused_recipients = unused_result.data if unused_result.success else []
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


def render_sending_progress(api: APIClient, user_id: int):
    """Render the email sending progress UI."""
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
            api.send_emails_stream(user_id, recipient_ids, subject, dry_run)
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


def render_send_results():
    """Render the results from a previous send operation."""
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
