import streamlit as st
import requests
import pandas as pd
import json
import os

# Configuration
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")

st.set_page_config(
    page_title="CV Email Sender",
    page_icon="📧",
    layout="wide"
)

# Initialize session state
if "current_user" not in st.session_state:
    st.session_state.current_user = None
if "recipients" not in st.session_state:
    st.session_state.recipients = []


def load_users():
    """Load list of users from backend"""
    try:
        response = requests.get(f"{BACKEND_URL}/users/")
        if response.status_code == 200:
            return response.json()
    except:
        pass
    return []


def create_user(username, email):
    """Create a new user"""
    try:
        response = requests.post(
            f"{BACKEND_URL}/users/",
            json={"username": username, "email": email}
        )
        return response.status_code == 200
    except:
        return False


def upload_credentials(user_id, file):
    """Upload Gmail credentials"""
    try:
        files = {"file": file}
        response = requests.post(
            f"{BACKEND_URL}/users/{user_id}/credentials",
            files=files
        )
        return response.status_code == 200
    except:
        return False


def upload_resume(user_id, file):
    """Upload resume PDF"""
    try:
        files = {"file": file}
        response = requests.post(
            f"{BACKEND_URL}/users/{user_id}/resume",
            files=files
        )
        return response.status_code == 200
    except:
        return False


def load_template(user_id):
    """Load user's template"""
    try:
        response = requests.get(f"{BACKEND_URL}/users/{user_id}/template")
        if response.status_code == 200:
            return response.json()["content"]
    except:
        pass
    return ""


def save_template(user_id, content):
    """Save user's template"""
    try:
        response = requests.post(
            f"{BACKEND_URL}/users/{user_id}/template",
            data={"content": content}
        )
        return response.status_code == 200
    except:
        return False


def parse_csv(user_id, file):
    """Parse CSV and extract recipients"""
    try:
        files = {"file": file}
        response = requests.post(
            f"{BACKEND_URL}/users/{user_id}/parse-csv",
            files=files
        )
        if response.status_code == 200:
            return response.json()["recipients"]
    except Exception as e:
        st.error(f"Error parsing CSV: {e}")
    return []

def send_emails_stream(user_id, subject, template, recipients, dry_run=False):
    payload = {
                "user_id": user_id,
                "subject": subject,
                "template": template,
                "recipients_json": json.dumps(recipients),
                "dry_run": dry_run
            }
    
    with requests.post(f"{BACKEND_URL}/send-emails/stream", data=payload, stream=True) as response:
        if response.status_code != 200:
            st.error("Failed to start email sending")
        else:
            for line in response.iter_lines():
                if not line:
                    continue
                yield json.loads(line.decode("utf-8"))


def send_emails(user_id, subject, template, recipients, dry_run=False):
    """Send emails to recipients"""
    try:
        response = requests.post(
            f"{BACKEND_URL}/send-emails",
            data={
                "user_id": user_id,
                "subject": subject,
                "template": template,
                "recipients_json": json.dumps(recipients),
                "dry_run": dry_run
            }
        )
        if response.status_code == 200:
            return response.json()["results"]
    except Exception as e:
        st.error(f"Error sending emails: {e}")
    return []


def get_user_stats(user_id):
    """Get user statistics"""
    try:
        response = requests.get(f"{BACKEND_URL}/users/{user_id}/stats")
        if response.status_code == 200:
            return response.json()
    except:
        pass
    return {"total_sent": 0, "total_failed": 0, "total_emails": 0}


# Main UI
st.title("📧 CV Email Sender")

# Sidebar - User Selection
with st.sidebar:
    st.header("👤 User Selection")
    
    users = load_users()
    
    if users:
        user_options = {f"{u['username']} ({u['email']})": u for u in users}
        selected = st.selectbox(
            "Select User",
            options=list(user_options.keys()),
            key="user_select"
        )
        
        if selected:
            st.session_state.current_user = user_options[selected]
    
    st.divider()
    
    # Create new user
    with st.expander("➕ Create New User"):
        new_username = st.text_input("Username")
        new_email = st.text_input("Email")
        if st.button("Create User"):
            if new_username and new_email:
                if create_user(new_username, new_email):
                    st.success("User created!") # FIXME: not showing, need to be in st.session_state
                    st.rerun()
                else:
                    st.error("Failed to create user")
            else:
                st.error("Please fill all fields")
    
    # User stats
    if st.session_state.current_user:
        st.divider()
        st.subheader("📊 Statistics")
        stats = get_user_stats(st.session_state.current_user["id"])
        col1, col2 = st.columns(2)
        col1.metric("Sent", stats["total_sent"])
        col2.metric("Failed", stats["total_failed"])


# Main content
if not st.session_state.current_user:
    st.info("👈 Please select or create a user to get started")
    st.stop()

user_id = st.session_state.current_user["id"]
username = st.session_state.current_user["username"]

st.subheader(f"Welcome, {username}! 👋")

# Tabs
tab1, tab2, tab3 = st.tabs(["📤 Send Emails", "⚙️ Configuration", "📜 History"])

with tab1:
    st.header("Send Emails")
    
    # Email subject
    subject = st.text_input("Email Subject", placeholder="Candidature spontanée")
    
    # Template editor
    st.subheader("Email Template")
    template = st.text_area(
        "Template (use {salutation} and {company} as placeholders)",
        value=load_template(user_id),
        height=200
    )
    
    if st.button("💾 Save Template"):
        if save_template(user_id, template):
            st.success("Template saved!")
        else:
            st.error("Failed to save template")
    
    st.divider()
    
    # CSV Upload
    st.subheader("Upload Recipients CSV")
    st.info("CSV should have columns: Email, First Name, Last Name, Company (or Company Name for Emails)")
    
    csv_file = st.file_uploader("Choose CSV file", type=["csv"])
    
    if csv_file:
        if st.button("📥 Parse CSV"):
            recipients = parse_csv(user_id, csv_file)
            st.session_state.recipients = recipients
            st.success(f"Loaded {len(recipients)} recipients")
    
    # Display recipients
    if st.session_state.recipients:
        st.subheader(f"Recipients ({len(st.session_state.recipients)})")
        
        df = pd.DataFrame(st.session_state.recipients)
        st.dataframe(df, use_container_width=True)
        
        # Preview
        st.subheader("📝 Email Preview")
        preview_idx = st.selectbox("Select recipient to preview", range(len(st.session_state.recipients)))
        
        if preview_idx is not None:
            recipient = st.session_state.recipients[preview_idx]
            salutation = f"Monsieur {recipient['last_name']}"  # Simplified
            preview_body = template.format(salutation=salutation, company=recipient['company'])
            
            st.text_area("Preview", value=preview_body, height=200, disabled=True)
        
        st.divider()
        
        # Send options
        col1, col2 = st.columns(2)
        
        with col1:
            dry_run = st.checkbox("🧪 Dry Run (Don't actually send)", value=False)
        
        with col2:
            if st.button("📧 Send Emails", type="primary", use_container_width=True):
                if not subject:
                    st.error("Please enter an email subject")
                elif not template:
                    st.error("Please enter an email template")
                else:
                    with st.spinner("Sending emails..."):
                        # results = send_emails(user_id, subject, template, st.session_state.recipients, dry_run)
                        status_box = st.empty()
                        log_box = st.container()
                        progress = st.progress(0)
                        sent = 0
                        failed = 0
                        skipped = 0
                        total = len(recipients)
                        for i, event in enumerate(send_emails_stream(user_id, subject, template, st.session_state.recipients, dry_run)):
                            # Update UI incrementally
                            with log_box:
                                st.write(event)

                            status_box.info(
                                f"Last email: {event.get('email')} → {event.get('status')}"
                            )

                            match event["status"]:
                                case "sent":
                                    sent += 1
                                case "failed":
                                    failed += 1
                                case "skipped":
                                    skipped += 1
                            progress.progress((i + 1) / total)

                        # # Display results
                        # st.subheader("Results")
                        
                        # sent = [r for r in results if r["status"] == "sent"]
                        # failed = [r for r in results if r["status"] == "failed"]
                        # skipped = [r for r in results if r["status"] == "skipped"]
                        
                        col1, col2, col3 = st.columns(3)
                        col1.metric("✅ Sent", sent)
                        col2.metric("❌ Failed", failed)
                        col3.metric("⏭️ Skipped", skipped)
                        
                        if failed:
                            st.error("Failed emails:")
                            for r in failed:
                                st.write(f"- {r['email']}: {r['message']}")
                        
                        if dry_run:
                            st.info("Dry run completed - no emails were actually sent")
                        else:
                            st.success("Email sending completed!")

with tab2:
    st.header("Configuration")
    
    st.subheader("📁 Upload Gmail Credentials")
    st.info("Upload your OAuth 2.0 credentials JSON file from Google Cloud Console")
    credentials_file = st.file_uploader("Choose credentials file", type=["json"], key="creds")
    
    if credentials_file:
        if st.button("Upload Credentials"):
            if upload_credentials(user_id, credentials_file):
                st.success("Credentials uploaded successfully!")
            else:
                st.error("Failed to upload credentials")
    
    st.divider()
    
    st.subheader("📄 Upload Resume")
    resume_file = st.file_uploader("Choose resume PDF", type=["pdf"])
    
    if resume_file:
        if st.button("Upload Resume"):
            if upload_resume(user_id, resume_file):
                st.success("Resume uploaded successfully!")
            else:
                st.error("Failed to upload resume")

with tab3:
    st.header("Email History")
    st.info("History feature coming soon!")
    
    # TODO: Implement email logs display
    stats = get_user_stats(user_id)
    st.write(f"Total emails sent: {stats['total_sent']}")
    st.write(f"Total emails failed: {stats['total_failed']}")

# Footer
st.divider()
st.caption("CV Email Sender - Made with Streamlit & FastAPI")