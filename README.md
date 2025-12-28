# CV Email Sender - Web Application

Modern web-based CV email sender with multi-user support, built with Streamlit and FastAPI.

## Features

- ✅ **Multi-user support** - Each user has isolated data, credentials, and email history
- 📧 **Gmail Integration** - Send emails via Gmail API
- 📊 **Email tracking** - Track sent, failed, and skipped emails
- 🎨 **Modern UI** - Clean Streamlit interface
- 🔄 **Template management** - Save and reuse email templates per user
- 👤 **Gender detection** - Automatic salutation (Monsieur/Madame) based on first name
- 🧪 **Dry run mode** - Preview emails before sending
- 📈 **Statistics** - Track total emails sent per user

## Prerequisites

- Docker Desktop (Windows/Mac)
- Google Cloud Console project with Gmail API enabled
- OAuth 2.0 credentials (download as JSON from Google Cloud Console)

## Project Structure

```
cv-email-sender/
├── docker-compose.yml
├── start.bat              # Windows startup script
├── start.sh               # Mac/Linux startup script
├── stop.bat               # Windows stop script
├── stop.sh                # Mac/Linux stop script
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── main.py           # FastAPI application
│   ├── database.py       # SQLAlchemy models
│   └── gmail_service.py  # Gmail API integration
├── frontend/
│   ├── Dockerfile
│   ├── requirements.txt
│   └── app.py            # Streamlit application
├── data/                 # SQLite database and user resumes
└── credentials/          # Gmail credentials and tokens per user
```

## Setup Instructions

### 1. Google Cloud Console Setup

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select existing one
3. Enable Gmail API:
   - Navigate to "APIs & Services" > "Library"
   - Search for "Gmail API"
   - Click "Enable"
4. Create OAuth 2.0 credentials:
   - Go to "APIs & Services" > "Credentials"
   - Click "Create Credentials" > "OAuth client ID"
   - Application type: "Desktop app"
   - Download the JSON file

### 2. Application Setup

#### On Windows:

1. Install Docker Desktop
2. Clone/download this project
3. Double-click `start.bat`
4. Wait for containers to build and start
5. Open browser to: http://localhost:8501

#### On Mac:

1. Install Docker Desktop
2. Clone/download this project
3. Make script executable: `chmod +x start.sh`
4. Run: `./start.sh`
5. Open browser to: http://localhost:8501

### 3. First Time Usage

1. **Create a user**:
   - In the sidebar, expand "Create New User"
   - Enter username and email
   - Click "Create User"

2. **Configure user**:
   - Go to "Configuration" tab
   - Upload your Gmail OAuth credentials JSON file
   - Upload your CV (PDF format)

3. **First email authentication**:
   - When you send your first email, a browser window will open
   - Sign in with your Gmail account
   - Grant permissions
   - The token will be saved for future use

4. **Prepare recipients CSV**:
   - Create a CSV file with these columns:
     - `Email`: Recipient email address
     - `First Name`: First name of recipient
     - `Last Name`: Last name of recipient
     - `Company`: Company name (or `Company Name for Emails`)

5. **Send emails**:
   - Go to "Send Emails" tab
   - Enter email subject
   - Edit email template (use `{salutation}` and `{company}` placeholders)
   - Upload CSV file and click "Parse CSV"
   - Review recipients and preview emails
   - Choose "Dry Run" to test without sending
   - Click "Send Emails"

## Usage

### Multi-User Workflow

1. Each team member creates their own user account
2. Each user uploads their own:
   - Gmail credentials
   - Resume/CV
   - Email template
3. Users can switch between accounts in the sidebar
4. Email history and statistics are tracked per user

### Template Variables

Use these placeholders in your email template:

- `{salutation}` - Auto-generated as "Monsieur LastName" or "Madame LastName"
- `{company}` - Company name from CSV

Example template:
```
Bonjour {salutation},

Je me permets de vous contacter concernant une opportunité au sein de {company}. 
Vous trouverez ci-joint mon CV.

Cordialement,
Votre Nom
```

### CSV Format

Your CSV should look like this:

```csv
Email,First Name,Last Name,Company
john.doe@example.com,John,Doe,Acme Corp
jane.smith@test.com,Jane,Smith,Tech Solutions
```

## Stopping the Application

### Windows:
- Double-click `stop.bat`
- Or press `Ctrl+C` in the terminal running the app

### Mac:
- Run `./stop.sh`
- Or press `Ctrl+C` in the terminal running the app

## Data Persistence

All data is stored locally in:

- `./data/` - SQLite database and user resumes
- `./credentials/` - Gmail OAuth tokens and credentials

This data persists between application restarts.

## Troubleshooting

### "Docker is not running"
- Start Docker Desktop and wait for it to fully load
- Try the start script again

### "Failed to upload credentials"
- Ensure the JSON file is a valid OAuth 2.0 credentials file from Google Cloud Console
- Check that Gmail API is enabled in your Google Cloud project

### "Failed to send email"
- Check your internet connection
- Ensure you've completed OAuth authentication (browser popup on first send)
- Verify the recipient email addresses are valid
- Check Gmail API quotas in Google Cloud Console

### Port already in use
- If port 8501 or 8000 is in use, modify `docker-compose.yml`:
  ```yaml
  ports:
    - "8502:8501"  # Change external port
  ```

## API Endpoints

The backend runs on `http://localhost:8000` and provides:

- `GET /users/` - List all users
- `POST /users/` - Create new user
- `POST /users/{user_id}/credentials` - Upload Gmail credentials
- `POST /users/{user_id}/resume` - Upload resume
- `GET /users/{user_id}/template` - Get user's template
- `POST /users/{user_id}/template` - Save user's template
- `POST /users/{user_id}/parse-csv` - Parse CSV file
- `POST /send-emails` - Send emails
- `GET /users/{user_id}/stats` - Get user statistics

API documentation: http://localhost:8000/docs

## Development

To modify the code:

1. Edit files in `backend/` or `frontend/`
2. Restart the containers: `docker-compose restart`
3. Or use hot-reload (already configured):
   - Backend: FastAPI auto-reloads on file changes
   - Frontend: Streamlit auto-reloads on file changes

## Security Notes

⚠️ **Important**: This application is designed for LOCAL use only.

- Gmail credentials and tokens are stored locally
- No authentication/authorization between frontend and backend
- SQLite database is not encrypted
- Do not expose ports 8000 or 8501 to the internet
- Do not commit credentials or tokens to version control

## License

MIT License - Feel free to modify and use as needed.

## Support

For issues or questions:
1. Check the troubleshooting section above
2. Review Docker logs: `docker-compose logs`
3. Check individual service logs: `docker-compose logs backend` or `docker-compose logs frontend`