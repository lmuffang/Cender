"""Cender - CV/Resume Email Sender Frontend Application."""

import os
import streamlit as st

from state import init_session_state
from api.client import APIClient
from components import sidebar, send_tab, config_tab, history_tab

# Configuration
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")

# Initialize
st.set_page_config(page_title="Cender", page_icon="📧", layout="wide")
init_session_state()
api = APIClient(BACKEND_URL)

# Main UI
st.title("📧 Cender")

# Sidebar - User Selection
sidebar.render(api)

# Main content
if not st.session_state.current_user:
    st.info("👈 Please select or create a user to get started")
    st.stop()

user_id = st.session_state.current_user["id"]
username = st.session_state.current_user["username"]

# Block UI while sending emails
if st.session_state.sending_emails:
    send_tab.render_sending_progress(api, user_id)
    st.stop()

# Show results from previous send operation
if st.session_state.send_results:
    send_tab.render_send_results()

st.subheader(f"Welcome, {username}! 👋")

# Tabs
tab1, tab2, tab3 = st.tabs(["📤 Send Emails", "⚙️ Configuration", "📜 History"])

with tab1:
    send_tab.render(api, user_id)

with tab2:
    config_tab.render(api, user_id)

with tab3:
    history_tab.render(api, user_id)

# Footer
st.divider()
st.caption("Cender - The resume sender made with Streamlit & FastAPI")
