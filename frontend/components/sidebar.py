"""Sidebar component with user selection, stats, and delete functionality."""

import streamlit as st
from api.client import APIClient
from state import handle_user_switch


def render(api: APIClient):
    """Render the sidebar component."""
    with st.sidebar:
        st.header("👤 User Selection")

        result = api.list_users()
        users = result.data if result.success else []

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
                if handle_user_switch(new_user):
                    st.rerun()

        st.divider()

        # Create new user
        _render_create_user(api)

        # Show success message if user was just created
        if st.session_state.user_created:
            st.success("User created successfully!")
            st.session_state.user_created = False

        # User stats and delete
        if st.session_state.current_user:
            _render_user_stats(api)
            _render_delete_user(api)


def _render_create_user(api: APIClient):
    """Render the create user form."""
    with st.expander("➕ Create New User"):
        new_username = st.text_input("Username", key="new_username")
        new_email = st.text_input("Email", key="new_email")
        if st.button("Create User"):
            if new_username and new_email:
                result = api.create_user(new_username, new_email)
                if result.success:
                    st.session_state.user_created = True
                    st.success("User created! Refreshing...")
                    st.rerun()
                else:
                    st.error(f"Failed to create user: {result.error}")
            else:
                st.error("Please fill all fields")


def _render_user_stats(api: APIClient):
    """Render user statistics."""
    st.divider()
    st.subheader("Statistics")
    result = api.get_user_stats(st.session_state.current_user["id"])
    stats = result.data
    col1, col2 = st.columns(2)
    col1.metric("Sent (logged)", stats["total_sent"])
    col2.metric("Failed", stats["total_failed"])
    st.caption("Stats based on email logs. Deleting logs resets these counts.")


def _render_delete_user(api: APIClient):
    """Render the delete user section."""
    st.divider()
    with st.expander("🗑️ Delete User", expanded=False):
        result = api.get_user_stats(st.session_state.current_user["id"])
        stats = result.data

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
                result = api.delete_user(st.session_state.current_user["id"])
                if result.success:
                    st.success(result.data.get("message", "User deleted successfully!"))
                    st.session_state.current_user = None
                    st.rerun()
                else:
                    st.error(f"Failed to delete user: {result.error}")
            else:
                st.error("Username doesn't match. Please type the exact username to confirm.")
