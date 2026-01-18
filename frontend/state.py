"""Session state management for Streamlit."""

import streamlit as st


def init_session_state():
    """Initialize all session state variables with defaults."""
    defaults = {
        "current_user": None,
        "user_created": False,
        "creds_upload_key": 0,
        "resume_upload_key": 0,
        "csv_upload_key": 0,
        "sending_emails": False,
        "send_results": None,
        "send_data": None,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def clear_sending_state():
    """Clear email sending related state."""
    st.session_state.send_results = None
    st.session_state.sending_emails = False
    st.session_state.send_data = None


def clear_gmail_auth_state():
    """Clear Gmail auth related state."""
    if "gmail_auth_url" in st.session_state:
        del st.session_state["gmail_auth_url"]
    if "gmail_auth_code" in st.session_state:
        del st.session_state["gmail_auth_code"]


def handle_user_switch(new_user: dict):
    """Handle switching to a new user."""
    if st.session_state.current_user is None:
        st.session_state.current_user = new_user
        return False

    if st.session_state.current_user["id"] != new_user["id"]:
        st.session_state.current_user = new_user
        clear_sending_state()
        clear_gmail_auth_state()
        return True

    return False
