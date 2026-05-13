import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

RECIPIENT = "info@cumbia.com.au"


def send_reservation_email(reservation: dict, phone: str) -> bool:
    sender = os.environ.get("GMAIL_SENDER", RECIPIENT)
    password = os.environ.get("GMAIL_APP_PASSWORD", "")

    if not password:
        print("[email] GMAIL_APP_PASSWORD not set — skipping email")
        return False

    date = reservation.get("date", "—")
    time = reservation.get("time", "—")
    name = reservation.get("name", "—")
    guests = reservation.get("party_size", "—")
    notes = reservation.get("notes") or "None"

    subject = f"New WhatsApp Reservation — {name} | {date} {time}"

    body = f"""
New reservation received via WhatsApp:

  Name:       {name}
  Date:       {date}
  Time:       {time}
  Guests:     {guests}
  Phone:      {phone}
  Notes:      {notes}

This booking was confirmed automatically by the WhatsApp agent.
"""

    msg = MIMEMultipart()
    msg["From"] = sender
    msg["To"] = RECIPIENT
    msg["Subject"] = subject
    msg.attach(MIMEText(body.strip(), "plain"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(sender, password)
            server.sendmail(sender, RECIPIENT, msg.as_string())
        print(f"[email] Reservation email sent to {RECIPIENT}")
        return True
    except Exception as e:
        print(f"[email] Failed to send email: {e}")
        return False
