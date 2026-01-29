"""Send emails tab component."""

import re

import pandas as pd
import streamlit as st

from api.client import APIClient

# Valid placeholders that can be used in templates
VALID_PLACEHOLDERS = {"salutation", "company", "company_name"}


def _validate_template_placeholders(template: str) -> list[str]:
    """
    Validate that template only uses known placeholders.

    Returns list of invalid placeholder names found.
    """
    # Find all {placeholder} patterns
    found_placeholders = re.findall(r"\{(\w+)\}", template)
    invalid = [p for p in found_placeholders if p not in VALID_PLACEHOLDERS]
    return invalid


def _clear_recipient_selection():
    """Clear recipient selection when filter changes."""
    if "recipient_selection" in st.session_state:
        st.session_state.recipient_selection = []
    # Reset send confirmation state when filter changes
    if "send_confirmed" in st.session_state:
        st.session_state.send_confirmed = False


def render(api: APIClient, user_id: int):
    """Render the send emails tab."""
    st.header("Send Emails")

    result = api.get_template(user_id)
    template = result.data
    template_content = template.get("content", "") if template else ""
    subject = template.get("subject", "") if template else ""

    # Email subject
    subject = st.text_input(
        "Email Subject",
        placeholder="Candidature spontanée",
        value=subject,
        key="email_subject",
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
            # Validate placeholders before saving
            invalid_placeholders = _validate_template_placeholders(template_content)
            if invalid_placeholders:
                st.error(
                    f"Invalid placeholder(s): {', '.join('{' + p + '}' for p in invalid_placeholders)}. "
                    f"Valid placeholders are: {{salutation}}, {{company}}, {{company_name}}"
                )
            else:
                result = api.save_template(user_id, template_content, subject)
                if result.success:
                    st.success("Template saved!")
                else:
                    st.error(f"Failed to save template: {result.error}")
    with col_info:
        st.caption("💡 Valid placeholders: {salutation}, {company}")

    st.divider()

    # CSV Upload
    _render_csv_upload(api, user_id)

    # Display recipients
    _render_recipients(api, user_id, template_content, subject)


def _render_csv_upload(api: APIClient, user_id: int):
    """Render CSV upload section."""
    st.subheader("Upload Recipients CSV")
    st.info("CSV should have columns: Email, First Name, Last Name, Company (or Company Name)")

    csv_file = st.file_uploader(
        "Choose CSV file", type=["csv"], key=f"csv_{st.session_state.csv_upload_key}"
    )

    if csv_file and st.button("📥 Import CSV"):
        result = api.import_recipients_csv(user_id, csv_file)
        if result.success:
            created = result.data.get("created", 0)
            total = result.data.get("total", 0)
            skipped = result.data.get("skipped", [])

            st.success(f"Added {created} new recipients! ({total} processed in total)")

            # Show skipped rows if any
            if skipped:
                with st.expander(f"Skipped {len(skipped)} rows", expanded=True):
                    for skip_info in skipped:
                        st.warning(f"Row {skip_info['row']}: {skip_info['reason']}")

            st.session_state.csv_upload_key += 1
            st.rerun()
        else:
            st.error(f"Error importing CSV: {result.error}")


def _render_recipients(api: APIClient, user_id: int, template_content: str, subject: str):
    """Render recipients list and send functionality."""
    # Initialize send confirmation state
    if "send_confirmed" not in st.session_state:
        st.session_state.send_confirmed = False

    # Filter recipients - default to "Unused" to prevent accidental mass sends
    filter_option = st.radio(
        "Filter recipients",
        options=["All", "Used", "Unused"],
        index=2,  # Default to "Unused"
        horizontal=True,
        key="recipient_filter",
        on_change=_clear_recipient_selection,
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

    # Get email logs to show sent status
    logs_result = api.get_email_logs(user_id, limit=10000)
    email_logs = logs_result.data if logs_result.success else []

    # Create lookup for sent status by recipient email
    sent_status_by_email = {}
    for log in email_logs:
        if log.get("status") == "sent":
            email = log.get("recipient_email")
            sent_at = log.get("sent_at")
            if email and (
                email not in sent_status_by_email or sent_at > sent_status_by_email[email]
            ):
                sent_status_by_email[email] = sent_at

    # Display recipients with selection
    df = pd.DataFrame(displayed_recipients)

    # Multi-select recipients
    selected_indices = st.multiselect(
        "Select recipients to send emails to",
        options=range(len(displayed_recipients)),
        format_func=lambda i: f"{displayed_recipients[i].get('email', 'N/A')} - {displayed_recipients[i].get('first_name', '')} {displayed_recipients[i].get('last_name', '')}",
        key="recipient_selection",
    )

    # Show clear message when no selection
    if not selected_indices:
        st.caption("No recipients selected - all displayed recipients will be targeted")

    # Add status column to dataframe
    df["status"] = df["email"].apply(lambda email: sent_status_by_email.get(email, "Not sent"))

    # Format status column - convert timestamps to readable format
    def format_status(status):
        if status == "Not sent":
            return status
        # It's a timestamp string
        try:
            return f"Sent: {status[:10]}"
        except Exception:
            return str(status)

    df["status"] = df["status"].apply(format_status)

    st.dataframe(
        df[["email", "first_name", "last_name", "company", "status"]],
        use_container_width=True,
    )

    # Preview - only save when button clicked
    _render_preview(api, user_id, displayed_recipients, subject, template_content)

    st.divider()

    dry_run = st.checkbox("Dry Run (Don't actually send)", value=False, key="dry_run")

    st.divider()

    # Send button with confirmation
    _render_send_button(
        api,
        user_id,
        displayed_recipients,
        selected_indices,
        subject,
        template_content,
        dry_run,
    )


def _render_preview(
    api: APIClient,
    user_id: int,
    displayed_recipients: list,
    subject: str,
    template_content: str,
):
    """Render email preview section."""
    if not displayed_recipients:
        return

    st.subheader("Email Preview")
    preview_idx = st.selectbox(
        "Select recipient for preview",
        options=range(len(displayed_recipients)),
        format_func=lambda i: displayed_recipients[i].get("email", "N/A"),
        key="preview_recipient",
    )

    # Use a button to trigger preview (and auto-save)
    if st.button("Generate Preview"):
        if not subject:
            st.warning("Enter a subject to see preview")
            return

        if preview_idx is None:
            st.warning("Select a recipient for preview")
            return

        # Validate placeholders before preview
        invalid_placeholders = _validate_template_placeholders(template_content)
        if invalid_placeholders:
            st.error(
                f"Invalid placeholder(s): {', '.join('{' + p + '}' for p in invalid_placeholders)}. "
                f"Fix before previewing."
            )
            return

        recipient = displayed_recipients[preview_idx]
        recipient_id = recipient.get("id")

        if not recipient_id:
            st.warning("Recipient ID not found")
            return

        # Auto-save template before preview to show current edits
        with st.spinner("Saving template..."):
            save_result = api.save_template(user_id, template_content, subject)
            if not save_result.success:
                st.warning("Could not save template for preview")
                return

        result = api.get_email_preview(user_id, recipient_id, subject)
        if result.success and result.data:
            st.session_state.preview_data = result.data
        else:
            st.warning("Could not generate preview. Make sure template is saved.")
            return

    # Show cached preview if available
    if "preview_data" in st.session_state and st.session_state.preview_data:
        preview_data = st.session_state.preview_data
        st.text_area(
            "Preview",
            value=preview_data.get("body", ""),
            height=200,
            disabled=True,
            key="preview_body",
        )
        attachment = preview_data.get("attachment_filename")
        if attachment:
            st.caption(f"Attachment: {attachment}")
        else:
            st.caption("No resume attached")


def _render_send_button(
    api: APIClient,
    user_id: int,
    displayed_recipients: list,
    selected_indices: list,
    subject: str,
    template_content: str,
    dry_run: bool,
):
    """Render the send emails button with validation and confirmation."""

    # Determine target recipients for this render (always recalculate to stay fresh)
    if selected_indices:
        target_count = len(selected_indices)
        target_desc = f"{target_count} selected recipient{'s' if target_count != 1 else ''}"
        # Store the actual IDs to use, not indices
        target_recipient_ids = [
            displayed_recipients[i]["id"] for i in selected_indices if i < len(displayed_recipients)
        ]
    else:
        # Will send to all unused - fetch once and cache for this render
        unused_result = api.list_recipients(user_id, used=False)
        unused_recipients = unused_result.data if unused_result.success else []
        target_count = len(unused_recipients)
        target_desc = f"all {target_count} unused recipient{'s' if target_count != 1 else ''}"
        target_recipient_ids = [r["id"] for r in unused_recipients]

    # Two-step confirmation flow
    if not st.session_state.send_confirmed:
        # First step: Show send button
        if st.button(f"Send Emails to {target_desc}", type="primary", use_container_width=True):
            # Validation checks
            if not subject:
                st.error("Please enter an email subject")
                return
            if not template_content:
                st.error("Please enter an email template")
                return
            if target_count == 0:
                st.warning("No recipients to send to.")
                return

            # Validate placeholders before sending
            invalid_placeholders = _validate_template_placeholders(template_content)
            if invalid_placeholders:
                st.error(
                    f"Invalid placeholder(s): {', '.join('{' + p + '}' for p in invalid_placeholders)}. "
                    f"Valid placeholders are: {{salutation}}, {{company}}, {{company_name}}. "
                    f"Fix your template before sending."
                )
                return

            # Store the recipient IDs at confirmation time to prevent stale data
            st.session_state.send_confirmed = True
            st.session_state.send_target_count = target_count
            st.session_state.send_target_desc = target_desc
            st.session_state.send_recipient_ids = target_recipient_ids
            st.rerun()
    else:
        # Verify stored data is still valid
        stored_count = st.session_state.get("send_target_count", 0)
        stored_ids = st.session_state.get("send_recipient_ids", [])

        if not stored_ids or stored_count == 0:
            st.error("Session data lost. Please try again.")
            st.session_state.send_confirmed = False
            st.rerun()
            return

        # Second step: Show confirmation warning and confirm button
        st.warning(
            f"You are about to send emails to **{stored_count}** recipient{'s' if stored_count != 1 else ''}. This action cannot be undone."
        )

        should_send = False
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Cancel", use_container_width=True):
                st.session_state.send_confirmed = False
                st.rerun()
        with col2:
            if st.button(
                f"Confirm Send ({stored_count})",
                type="primary",
                use_container_width=True,
            ):
                should_send = True
        if should_send:
            # Use the stored recipient IDs from confirmation time
            _execute_send(api, user_id, stored_ids, subject, template_content, dry_run)


def _execute_send(
    api: APIClient,
    user_id: int,
    recipient_ids: list[int],
    subject: str,
    template_content: str,
    dry_run: bool,
):
    """Execute the actual email sending after confirmation."""
    # Reset confirmation state at start
    st.session_state.send_confirmed = False

    # Pre-flight checks (skip for dry run)
    if not dry_run:
        files_result = api.get_files_status(user_id)
        preflight_status = files_result.data

        gmail_result = api.get_gmail_status(user_id)
        gmail_preflight = gmail_result.data

        if not preflight_status["has_credentials"]:
            st.error(
                "Gmail credentials not uploaded. Please go to Configuration tab and upload your credentials.json file."
            )
            return
        if not gmail_preflight["connected"]:
            error_detail = gmail_preflight.get("error", "Unknown error")
            st.error(
                f"Gmail not connected. Please go to Configuration tab to connect your Gmail account. ({error_detail})"
            )
            return
        if not preflight_status["has_resume"]:
            st.error(
                "Resume not uploaded. Please go to Configuration tab and upload your resume PDF."
            )
            return

    # Save template first
    save_result = api.save_template(user_id, template_content, subject)
    if not save_result.success:
        st.error("Failed to save template. Please try again.")
        return

    if not recipient_ids:
        st.warning("No recipients to send to.")
        return

    # Send emails directly using st.status()
    status_label = "Dry run in progress..." if dry_run else "Sending emails..."
    with st.status(status_label, expanded=True) as status:
        progress = st.progress(0)
        log_container = st.container()
        sent = 0
        failed = 0
        skipped = 0
        total = len(recipient_ids)
        errors = []

        for i, event in enumerate(api.send_emails_stream(user_id, recipient_ids, subject, dry_run)):
            if "error" in event:
                status.update(label=f"Error: {event['error']}", state="error")
                st.error(event["error"])
                return

            # Update log
            with log_container:
                status_text = f"{event.get('email', 'N/A')} -> {event.get('status', 'unknown')}"
                if event.get("message"):
                    status_text += f" ({event.get('message')})"
                st.text(status_text)

            event_status = event.get("status", "")
            if event_status == "sent":
                sent += 1
            elif event_status == "failed":
                failed += 1
                errors.append(
                    {
                        "email": event.get("email", "N/A"),
                        "message": event.get("message", "Unknown error"),
                    }
                )
            elif event_status == "skipped":
                skipped += 1
            elif event_status == "dry_run":
                sent += 1  # Count dry_run as "sent" for display purposes

            progress.progress((i + 1) / total if total > 0 else 1)

        # Show results with appropriate labels
        st.divider()
        col1, col2, col3 = st.columns(3)

        # Use different labels for dry run vs actual send
        if dry_run:
            col1.metric("Would Send", sent)
        else:
            col1.metric("Sent", sent)
        col2.metric("Failed", failed)
        col3.metric("Skipped", skipped)

        if errors:
            with st.expander("Failed emails details"):
                for err in errors:
                    st.write(f"- {err['email']}: {err['message']}")

        if dry_run:
            status.update(label="Dry run completed", state="complete")
            st.info("Dry run completed - no emails were actually sent")
        else:
            status.update(label="Sending complete!", state="complete")
            st.success("Email sending completed!")
            # Refresh recipient list after send to show updated status
            st.rerun()
