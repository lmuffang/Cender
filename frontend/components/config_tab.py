"""Configuration tab component."""

import streamlit as st
from api.client import APIClient


def render(api: APIClient, user_id: int):
    """Render the configuration tab."""
    st.header("Configuration")

    # Get status information
    gmail_result = api.get_gmail_status(user_id)
    gmail_status = gmail_result.data

    files_result = api.get_files_status(user_id)
    files_status = files_result.data

    # Setup Status Overview
    _render_status_overview(gmail_status, files_status)

    st.divider()

    # Credentials Upload Section
    _render_credentials_upload(api, user_id, files_status)

    st.divider()

    # OAuth Authorization Section
    _render_gmail_auth(api, user_id, gmail_status, files_status)

    st.divider()

    # Resume Upload Section
    _render_resume_upload(api, user_id, files_status)

    st.divider()

    # Delete Recipients Section
    _render_manage_recipients(api, user_id)


def _render_status_overview(gmail_status: dict, files_status: dict):
    """Render setup status overview."""
    st.subheader("Setup Status")
    col1, col2, col3 = st.columns(3)

    with col1:
        if files_status["has_credentials"]:
            st.success("Credentials: Uploaded")
        else:
            st.error("Credentials: Missing")

    with col2:
        if gmail_status["connected"]:
            st.success("Gmail: Connected")
        elif gmail_status["has_credentials"]:
            st.warning("Gmail: Not authorized")
        else:
            st.error("Gmail: Not connected")

    with col3:
        if files_status["has_resume"]:
            st.success("Resume: Uploaded")
        else:
            st.error("Resume: Missing")


def _render_credentials_upload(api: APIClient, user_id: int, files_status: dict):
    """Render credentials upload section."""
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
            result = api.upload_credentials(user_id, credentials_file)
            if result.success:
                st.success("Credentials uploaded successfully!")
                st.session_state.creds_upload_key += 1
                st.rerun()
            else:
                st.error(f"Failed to upload credentials: {result.error}")


def _render_gmail_auth(api: APIClient, user_id: int, gmail_status: dict, files_status: dict):
    """Render Gmail OAuth authorization section."""
    st.subheader("2. Connect to Gmail")
    if not files_status["has_credentials"]:
        st.info("Please upload credentials first")
    elif gmail_status["connected"]:
        st.success("Already connected!")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Reconnect", help="Use this if you need to re-authorize"):
                result = api.get_gmail_auth_url(user_id)
                if result.success:
                    st.session_state["gmail_auth_url"] = result.data.get("auth_url")
                else:
                    st.error(f"Failed to get authorization URL: {result.error}")
        with col2:
            if st.button("Disconnect", help="Remove Gmail connection"):
                result = api.disconnect_gmail(user_id)
                if result.success:
                    st.success(result.data.get("message", "Disconnected!"))
                    st.rerun()
                else:
                    st.error(result.error)
    else:
        if st.button("Connect to Gmail"):
            result = api.get_gmail_auth_url(user_id)
            if result.success:
                st.session_state["gmail_auth_url"] = result.data.get("auth_url")
            else:
                st.error(f"Failed to get authorization URL: {result.error}")

    # Show authorization flow if URL is available
    if "gmail_auth_url" in st.session_state:
        _render_auth_flow(api, user_id)


def _render_auth_flow(api: APIClient, user_id: int):
    """Render the Gmail auth flow instructions."""
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
                result = api.complete_gmail_auth(user_id, auth_code)
                if result.success:
                    st.success(result.data.get("message", "Connected!"))
                    del st.session_state["gmail_auth_url"]
                    if "gmail_auth_code" in st.session_state:
                        del st.session_state["gmail_auth_code"]
                    st.rerun()
                else:
                    st.error(result.error)
            else:
                st.warning("Please paste the redirect URL")
    with col2:
        if st.button("Cancel"):
            del st.session_state["gmail_auth_url"]
            st.rerun()


def _render_resume_upload(api: APIClient, user_id: int, files_status: dict):
    """Render resume upload section."""
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
            result = api.upload_resume(user_id, resume_file)
            if result.success:
                st.success("Resume uploaded successfully!")
                st.session_state.resume_upload_key += 1
                st.rerun()
            else:
                st.error(f"Failed to upload resume: {result.error}")


def _render_manage_recipients(api: APIClient, user_id: int):
    """Render manage recipients section."""
    st.subheader("4. Manage Recipients")

    result = api.list_recipients(user_id)
    recipients = result.data if result.success else []
    recipients_count = len(recipients)

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
            result = api.delete_all_recipients(user_id)
            if result.success:
                st.success(f"Removed {result.data.get('count', 0)} recipients from your account.")
                st.rerun()
            else:
                st.error(f"Failed to remove recipients: {result.error}")
