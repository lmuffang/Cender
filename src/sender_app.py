import os
import base64
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

TEMPLATE_FILE = "template.txt"
SCOPES = ["https://www.googleapis.com/auth/gmail.send"]


def get_history_filename(credentails_path):
    credentials_name = os.path.splitext(os.path.basename(credentails_path))[0]
    return f"sent_mails_{credentials_name}.csv"


def load_sent_log(history_filename):
    if os.path.exists(history_filename):
        with open(history_filename, "r", encoding="utf-8") as f:
            return set(line.strip() for line in f if line.strip())
    return set()


def save_to_sent_log(email, history_filename):
    with open(history_filename, "a", encoding="utf-8") as f:
        f.write(email + "\n")


def authenticate_gmail(credentails_path: str):
    credentials_name = os.path.splitext(os.path.basename(credentails_path))[0]
    token_filename = f"token-{credentials_name}.json"
    creds = None
    if os.path.exists(token_filename):
        creds = Credentials.from_authorized_user_file(token_filename, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(credentails_path, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(token_filename, "w") as token:
            token.write(creds.to_json())
    return build("gmail", "v1", credentials=creds)


def load_template():
    if os.path.exists(TEMPLATE_FILE):
        try:
            with open(TEMPLATE_FILE, "r", encoding="utf-8") as f:
                return f.read()
        except:
            pass
    return "Bonjour {salutation},\n\nJe me permets de vous contacter concernant une opportunité au sein de {company}. Vous trouverez ci-joint mon CV.\n\nCordialement,\nVotre Nom"


def save_template(content):
    try:
        with open(TEMPLATE_FILE, "w", encoding="utf-8") as f:
            f.write(content)
    except:
        pass


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
        part.add_header(
            "Content-Disposition", f"attachment; filename={os.path.basename(resume_path)}"
        )
        msg.attach(part)

    raw_msg = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    return {"raw": raw_msg}, body


def send_email(service, message, recipient):
    try:
        service.users().messages().send(userId="me", body=message).execute()
        print(f"Email sent to {recipient}")
    except HttpError as error:
        print(f"Failed to send email to {recipient}: {error}")
        raise error


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
        tk.Entry(root, textvariable=self.credentials_path, width=50).grid(row=0, column=1)
        tk.Button(root, text="Parcourir", command=self.browse_credentials).grid(row=0, column=2)

        tk.Label(root, text="CV (PDF) :").grid(row=1, column=0, sticky="e")
        tk.Entry(root, textvariable=self.resume_path, width=50).grid(row=1, column=1)
        tk.Button(root, text="Parcourir", command=self.browse_resume).grid(row=1, column=2)

        tk.Label(root, text="Fichier CSV :").grid(row=2, column=0, sticky="e")
        tk.Entry(root, textvariable=self.csv_path, width=50).grid(row=2, column=1)
        tk.Button(root, text="Parcourir", command=self.browse_csv).grid(row=2, column=2)

        tk.Label(root, text="Sujet de l'e-mail :").grid(row=3, column=0, sticky="e")
        tk.Entry(root, textvariable=self.subject, width=50).grid(row=3, column=1, columnspan=2)

        tk.Checkbutton(
            root,
            text="Simmuler les emails (n'envoie pas les emails, affiche seulement)",
            variable=self.dry_run,
        ).grid(row=4, column=1, sticky="w")

        tk.Label(root, text="Modèle d'e-mail :").grid(row=5, column=0, sticky="ne")
        self.template_box = scrolledtext.ScrolledText(root, width=60, height=15)
        self.template_box.grid(row=5, column=1, columnspan=2)
        self.template_box.insert(tk.END, load_template())

        tk.Button(
            root,
            text="Envoyer les e-mails",
            command=lambda: self.send_emails(self.credentials_path.get()),
        ).grid(row=6, column=1, pady=10)

        self.log_frame = tk.Frame(root)
        self.log_frame.grid(row=7, column=0, columnspan=3, pady=(0, 10), sticky="nsew")

        self.log_box = scrolledtext.ScrolledText(
            self.log_frame,
            width=100,
            height=12,
            wrap='none',
            state='disabled',
            font=("Courier", 10)
        )
        self.log_box.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        x_scrollbar = tk.Scrollbar(self.log_frame, orient='horizontal', command=self.log_box.xview)
        x_scrollbar.pack(side=tk.BOTTOM, fill=tk.X)
        self.log_box.config(xscrollcommand=x_scrollbar.set)

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
        if g in ("male", "mostly_male"):
            return "Monsieur"
        elif g in ("female", "mostly_female"):
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

    def log(self, message):
        self.log_box.config(state='normal')
        self.log_box.insert(tk.END, message + '\n')
        self.log_box.see(tk.END)
        self.log_box.config(state='disabled')

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

        history_filename = get_history_filename(credentails_path=credentails_path)
        sent_emails = load_sent_log(history_filename)
        nb_mails_sent=0
        for _, row in df.iterrows():
            try:
                email = row.get("Email", "").strip()
                first_name = row.get("First Name", "").strip()
                last_name = row.get("Last Name", "").strip()
                company = row.get("Company", row.get("Company Name for Emails", "")).strip()

                if not email:
                    continue
                if email in sent_emails:
                    print(f"Skipping {email} (already sent)")
                    continue

                salutation = f"{self.guess_salutation(first_name)} {last_name}".strip()
                msg, body = create_message(email, salutation, company, template, resume, subject)

                if dry_run:
                    messagebox.showinfo(
                        title=f"Email Généré", message=f"Email : {email}\n\nObjet : {subject}\n\n{body}"
                    )
                    self.log(f"[INFO] Faux envoi réussi pour {row.get('Email', 'N/A')}")
                else:
                    try:
                        send_email(service, msg, email)
                        save_to_sent_log(email, history_filename)
                        sent_emails.add(email)
                        self.log(f"[INFO] Envoi réussi pour {row.get('Email', 'N/A')}")
                        nb_mails_sent+=1
                    except Exception as e:
                        messagebox.showerror("Erreure", f"Erreure lors de l'envoi: {e}")
            except Exception as e:
                self.log(f"[ERREUR] Envoi échoué pour {row.get('Email', 'N/A')}: {e}")

        if dry_run:
            messagebox.showinfo("Terminé", "Traitement terminé. Emails simulés.")
        else:
            messagebox.showinfo("Terminé", f"Traitement terminé. {nb_mails_sent} emails envoyés.")



if __name__ == "__main__":
    root = tk.Tk()
    app = App(root)
    root.mainloop()
