import os
import json
import base64
from datetime import datetime
import gspread
from google.oauth2.service_account import Credentials

SPREADSHEET_ID = "10RxL-POJ-lJRMYXoSEq4TdUllcg4mw3WnKMLLhNowM8"
SHEET_NAME = "Bookings_WA"

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

HEADERS = ["Timestamp", "Date", "Time", "Guests", "Name", "Phone", "Notes", "Status"]


def _get_sheet():
    creds_b64 = os.environ.get("GOOGLE_CREDENTIALS_B64")
    if creds_b64:
        creds_info = json.loads(base64.b64decode(creds_b64))
    else:
        creds_path = os.path.join(
            os.path.dirname(__file__),
            "..",
            "config",
            "spartan-perigee-494417-f5-service-account.json",
        )
        with open(creds_path) as f:
            creds_info = json.load(f)

    creds = Credentials.from_service_account_info(creds_info, scopes=SCOPES)
    gc = gspread.authorize(creds)
    spreadsheet = gc.open_by_key(SPREADSHEET_ID)

    try:
        sheet = spreadsheet.worksheet(SHEET_NAME)
    except gspread.WorksheetNotFound:
        sheet = spreadsheet.add_worksheet(title=SHEET_NAME, rows=1000, cols=len(HEADERS))
        sheet.append_row(HEADERS)

    return sheet


def save_reservation(data: dict, phone: str) -> bool:
    """Append a new booking row. Returns True on success."""
    try:
        sheet = _get_sheet()
        row = [
            datetime.now().strftime("%d/%m/%Y %H:%M"),
            data.get("date", ""),
            data.get("time", ""),
            data.get("party_size", ""),
            data.get("name", ""),
            phone,
            data.get("notes", ""),
            "Confirmed",
        ]
        sheet.append_row(row)
        return True
    except Exception as e:
        print(f"[sheets] Error saving reservation: {e}")
        return False
