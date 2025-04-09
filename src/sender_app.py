import os
import base64
import sys
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext
import pandas as pd
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google.oauth2.credentials import Credentials


def resource_path(filename):
    if hasattr(sys, "_MEIPASS"):
        return os.path.join(sys._MEIPASS, filename)  # PyInstaller temp dir
    return os.path.join(os.path.abspath("."), filename)

TEMPLATE_FILE = resource_path("template.txt")
SCOPES = ["https://www.googleapis.com/auth/gmail.send"]

def authenticate_gmail(credentails_path : str):
    creds = None
    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(credentails_path, SCOPES)
            creds = flow.run_local_server(port=0)
        with open("token.json", "w") as token:
            token.write(creds.to_json())
    return build("gmail", "v1", credentials=creds)

def load_template():
    if os.path.exists(TEMPLATE_FILE):
        with open(TEMPLATE_FILE, 'r', encoding='utf-8') as f:
            return f.read()
    return "Bonjour {salutation},\n\nJe me permets de vous contacter concernant une opportunité au sein de {company}. Vous trouverez ci-joint mon CV.\n\nCordialement,\nVotre Nom"

def save_template(content):
    with open(TEMPLATE_FILE, 'w', encoding='utf-8') as f:
        f.write(content)

def create_message(to_email, salutation, company, template, resume_path, subject):
    msg = MIMEMultipart()
    msg["To"] = to_email
    msg["Subject"] = subject

    body = template.format(salutation=salutation, company=company)
    msg.attach(MIMEText(body, "plain"))

    with open(resume_path, "rb") as attachment:
        part = MIMEBase("application", "octet-stream")
        part.set_payload(attachment.read())
        encoders.encode_base64(part)
        part.add_header("Content-Disposition", f"attachment; filename={os.path.basename(resume_path)}")
        msg.attach(part)

    raw_msg = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    return {"raw": raw_msg}, body

def send_email(service, message, recipient):
    try:
        service.users().messages().send(userId="me", body=message).execute()
        print(f"Email sent to {recipient}")
    except HttpError as error:
        print(f"Failed to send email to {recipient}: {error}")

class App:
    def __init__(self, root):
        self.root = root
        self.root.title("CV Email Sender")

        self.root.bind("<Map>", lambda event: self.root.focus_force())

        self.credentials_path = tk.StringVar()
        self.resume_path = tk.StringVar()
        self.csv_path = tk.StringVar()
        self.subject = tk.StringVar()
        self.dry_run = tk.BooleanVar()

        self.gender_detector = self.init_gender_detector()

        tk.Label(root, text="Identifials Gmail :").grid(row=0, column=0, sticky="e")
        tk.Entry(root, textvariable=self.resume_path, width=50).grid(row=0, column=1)
        tk.Button(root, text="Parcourir", command=self.browse_credentials).grid(row=0, column=2)

        tk.Label(root, text="CV (PDF) :").grid(row=1, column=0, sticky="e")
        tk.Entry(root, textvariable=self.resume_path, width=50).grid(row=1, column=1)
        tk.Button(root, text="Parcourir", command=self.browse_resume).grid(row=1, column=2)

        tk.Label(root, text="Fichier CSV :").grid(row=2, column=0, sticky="e")
        tk.Entry(root, textvariable=self.csv_path, width=50).grid(row=2, column=1)
        tk.Button(root, text="Parcourir", command=self.browse_csv).grid(row=2, column=2)

        tk.Label(root, text="Sujet de l'e-mail :").grid(row=3, column=0, sticky="e")
        tk.Entry(root, textvariable=self.subject, width=50).grid(row=3, column=1, columnspan=2)

        tk.Checkbutton(root, text="Dry run (n'envoie pas les emails, affiche seulement)", variable=self.dry_run).grid(row=4, column=1, sticky="w")

        tk.Label(root, text="Modèle d'e-mail :").grid(row=5, column=0, sticky="ne")
        self.template_box = scrolledtext.ScrolledText(root, width=60, height=15)
        self.template_box.grid(row=4, column=1, columnspan=2)
        self.template_box.insert(tk.END, load_template())

        tk.Button(root, text="Envoyer les e-mails", command=lambda: self.send_emails(self.credentials_path.get())).grid(row=6, column=1, pady=10)

    def init_gender_detector(self):
        try:
            import gender_guesser.detector as gender
            return gender.Detector()
        except:
            return None

    def guess_salutation(self, first_name):
        if not self.gender_detector:
            return "Monsieur"
        g = self.gender_detector.get_gender(first_name)
        if g in ('male', 'mostly_male'):
            return "Monsieur"
        elif g in ('female', 'mostly_female'):
            return "Madame"
        else:
            return "Monsieur"

    def browse_credentials(self):
        file = filedialog.askopenfilename(filetypes=[("JSON Files", "*.json")])
        self.root.after(100, self.root.focus_force)  # Delayed focus
        if file:
            self.credentials_path.set(file)

    def browse_resume(self):
        file = filedialog.askopenfilename(filetypes=[("PDF Files", "*.pdf")])
        self.root.after(100, self.root.focus_force)  # Delayed focus
        if file:
            self.resume_path.set(file)

    def browse_csv(self):
        file = filedialog.askopenfilename(filetypes=[("CSV Files", "*.csv")])
        self.root.after(100, self.root.focus_force)  # Delayed focus
        if file:
            self.csv_path.set(file)

    def send_emails(self, credentails_path):
        resume = self.resume_path.get()
        csv_file = self.csv_path.get()
        subject = self.subject.get()
        template = self.template_box.get("1.0", tk.END)
        dry_run = self.dry_run.get()

        if not all([resume, csv_file, subject.strip(), template.strip()]):
            messagebox.showerror("Informations manquantes", "Veuillez remplir tous les champs.")
            return

        save_template(template)
        df = pd.read_csv(csv_file, dtype=str)
        service = authenticate_gmail(credentails_path=credentails_path) if not dry_run else None

        for _, row in df.iterrows():
            email = row.get("Email", "").strip()
            first_name = row.get("First Name", "").strip()
            last_name = row.get("Last Name", "").strip()
            company = row.get("Company", row.get("Company Name for Emails", "")).strip()

            if not email:
                continue

            salutation = f"{self.guess_salutation(first_name)} {last_name}".strip()
            msg, body = create_message(email, salutation, company, template, resume, subject)

            if dry_run:
                print(f"\nTO: {email}\nSUBJECT: {subject}\nBODY:\n{body}\n")
            else:
                send_email(service, msg, email)
                pass

        messagebox.showinfo("Terminé", "Traitement terminé. Emails envoyés (ou simulés).")

if __name__ == "__main__":
    root = tk.Tk()
    app = App(root)
    root.mainloop()
