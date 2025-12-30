# Quick Start Guide

## 🚀 Get Running in 5 Minutes

### Step 1: Prerequisites
- [ ] Install [Docker Desktop](https://www.docker.com/products/docker-desktop/)
- [ ] Start Docker Desktop (wait until it says "Docker is running")
- [ ] Download your OAuth 2.0 credentials from [Google Cloud Console](https://console.cloud.google.com/)

### Step 2: Start the Application

**Windows:**
```bash
# Just double-click start.bat
```

**Mac/Linux:**
```bash
chmod +x start.sh
./start.sh
```

### Step 3: Open the App
- Open your browser to: **http://localhost:8501**
- You should see the Cender interface

### Step 4: First-Time Setup (One-time per user)

1. **Create your user** (in sidebar):
   - Click "Create New User"
   - Enter username: `john_doe`
   - Enter email: `john@example.com`
   - Click "Create User"

2. **Upload credentials** (Configuration tab):
   - Click "Choose credentials file"
   - Select your downloaded OAuth JSON file
   - Click "Upload Credentials"

3. **Upload your CV** (Configuration tab):
   - Click "Choose resume PDF"
   - Select your CV file
   - Click "Upload Resume"

### Step 5: Send Your First Batch

1. Go to **"Send Emails"** tab

2. **Edit the template**:
   ```
   Bonjour {salutation},
   
   Je me permets de vous contacter concernant une opportunité 
   au sein de {company}. Vous trouverez ci-joint mon CV.
   
   Cordialement,
   John Doe
   ```

3. **Prepare your CSV** (example: `recipients.csv`):
   ```csv
   Email,First Name,Last Name,Company
   jane.smith@example.com,Jane,Smith,Acme Corp
   bob.jones@test.com,Bob,Jones,Tech Solutions
   ```

4. **Upload and send**:
   - Enter subject: "Candidature spontanée"
   - Upload your CSV file
   - Click "Parse CSV"
   - ✅ Check "Dry Run" for first test
   - Click "Send Emails"

5. **First send - OAuth flow**:
   - A browser window will open
   - Sign in with your Gmail account
   - Grant permissions
   - Close the browser tab
   - Token is now saved for future sends

### Step 6: Send For Real

1. Uncheck "Dry Run"
2. Click "Send Emails"
3. Watch the progress in real-time!

## 🎉 That's It!

You're now ready to send CV emails at scale.

## 💡 Pro Tips

- **Multiple users**: Each person on your team can create their own account
- **Template per user**: Each user's template is saved automatically
- **History tracking**: Check the Statistics in sidebar to see your progress
- **Skip duplicates**: Already-sent emails are automatically skipped

## ⚠️ Important Notes

1. **Gmail API Limits**: 
   - Free tier: ~100 emails/day
   - Check your quotas: [Google Cloud Console](https://console.cloud.google.com/apis/api/gmail.googleapis.com/quotas)

2. **OAuth Token**: 
   - Token is saved after first authentication
   - Valid for several weeks
   - If expired, you'll be prompted to re-authenticate

3. **Data Location**:
   - Database: `./data/app.db`
   - Credentials: `./credentials/`
   - Your data persists between restarts

## 🛑 Stopping the App

**Windows:** Double-click `stop.bat` or press Ctrl+C

**Mac/Linux:** Run `./stop.sh` or press Ctrl+C

## 🆘 Common Issues

**"Docker is not running"**
- Open Docker Desktop
- Wait for it to fully start (whale icon in system tray)
- Try again

**"Port 8501 already in use"**
- Something else is using that port
- Edit `docker-compose.yml` and change `8501:8501` to `8502:8501`
- Access at http://localhost:8502

**"Failed to send email"**
- Check internet connection
- Verify OAuth was completed
- Check Gmail API is enabled in Google Cloud Console

**Need help?** Check the full README.md for detailed troubleshooting.

---

Happy job hunting! 🎯