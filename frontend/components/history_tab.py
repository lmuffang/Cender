"""Email history tab component."""

import pandas as pd
import streamlit as st

from api.client import APIClient


def render(api: APIClient, user_id: int):
    """Render the history tab."""
    st.header("Email History")

    # Stats overview
    result = api.get_user_stats(user_id)
    stats = result.data
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Sent", stats["total_sent"])
    col2.metric("Total Failed", stats["total_failed"])
    col3.metric("Total Skipped", stats["total_skipped"])
    col4.metric("Total Emails", stats["total_emails"])

    st.divider()

    # Reset/Delete email logs section
    _render_reset_logs(api, user_id)

    st.divider()

    # Email logs
    _render_email_logs(api, user_id)


def _render_reset_logs(api: APIClient, user_id: int):
    """Render the reset email logs section."""
    with st.expander("Reset Sent Emails", expanded=False):
        st.error(
            "**Warning:** Deleting email logs will mark those recipients as 'Unused' again. "
            "This means they can receive duplicate emails if you send again!"
        )
        st.info("This deletes the email logs. You can filter by recipient, status, or date.")

        col1, col2 = st.columns(2)

        with col1:
            reset_option = st.radio(
                "Reset options",
                options=["All sent emails", "By recipient", "By status", "Before date"],
                key="reset_option",
            )

        with col2:
            reset_recipient_id = None
            reset_status = None
            reset_date = None

            if reset_option == "By recipient":
                result = api.list_recipients(user_id)
                recipients = result.data if result.success else []
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
                    result = api.delete_email_logs(user_id, status="sent")
                elif reset_option == "By recipient":
                    if not reset_recipient_id:
                        st.error("Please select a recipient")
                        st.stop()
                    result = api.delete_email_logs(user_id, recipient_id=reset_recipient_id)
                elif reset_option == "By status":
                    result = api.delete_email_logs(user_id, status=reset_status)
                elif reset_option == "Before date":
                    result = api.delete_email_logs(user_id, before_date=reset_date)
                else:
                    result = api.delete_email_logs(user_id)

                if result.success:
                    st.success(f"✅ {result.data.get('message', 'Email logs deleted successfully')}")
                    st.rerun()
                else:
                    st.error(f"❌ Failed to delete logs: {result.error}")
            except Exception as e:
                st.error(f"❌ Failed to delete logs: {str(e)}")


def _render_email_logs(api: APIClient, user_id: int):
    """Render the email logs table."""
    limit = st.slider("Number of logs to display", min_value=10, max_value=500, value=100, step=10)
    result = api.get_email_logs(user_id, limit)
    logs = result.data if result.success else []

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
            result = api.delete_email_log(user_id, selected_log_id)
            if result.success:
                st.success("✅ Email log deleted successfully!")
                st.rerun()
            else:
                st.error(f"❌ Failed to delete email log: {result.error}")
    else:
        st.info("No email logs found")
