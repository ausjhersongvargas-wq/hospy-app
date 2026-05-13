import os

# Cargar .env
_env_file = os.path.join(os.path.dirname(__file__), ".env")
if os.path.exists(_env_file):
    with open(_env_file) as _f:
        for _line in _f:
            _line = _line.strip()
            if _line and not _line.startswith("#") and "=" in _line:
                _k, _, _v = _line.partition("=")
                os.environ[_k.strip()] = _v.strip()

from flask import Flask, request, abort
from twilio.twiml.messaging_response import MessagingResponse
from twilio.request_validator import RequestValidator

import sheets_client
import email_client
from conversation import ConversationManager

# Usa Groq si hay GROQ_API_KEY, sino Claude
if os.environ.get("GROQ_API_KEY"):
    import groq_client as claude_client
else:
    import claude_client

app = Flask(__name__)
conversations = ConversationManager()


def _validate_twilio(req):
    auth_token = os.environ.get("TWILIO_AUTH_TOKEN", "")
    validator = RequestValidator(auth_token)
    # Use X-Forwarded-Proto if behind a proxy (Railway)
    url = req.url.replace("http://", "https://") if req.headers.get("X-Forwarded-Proto") == "https" else req.url
    return validator.validate(url, req.form, req.headers.get("X-Twilio-Signature", ""))


@app.route("/webhook", methods=["POST"])
def webhook():
    if os.environ.get("TWILIO_VALIDATE", "true").lower() == "true":
        if not _validate_twilio(request):
            abort(403)

    phone = request.form.get("From", "unknown")
    body = (request.form.get("Body") or "").strip()

    if not body:
        return _twiml("")

    history = conversations.get_history(phone)

    try:
        reply, reservation = claude_client.get_response(history, body)
    except Exception as e:
        print(f"[agent] Claude error: {e}")
        reply = "Sorry, I'm having a technical issue right now. Please call us at (08) 8231 5000 or email info@cumbia.com.au"
        reservation = None

    if reservation:
        sheets_client.save_reservation(reservation, phone)
        email_client.send_reservation_email(reservation, phone)

    conversations.add_turn(phone, body, reply)

    return _twiml(reply)


def _twiml(message: str):
    resp = MessagingResponse()
    if message:
        resp.message(message)
    return str(resp), 200, {"Content-Type": "text/xml"}


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5001))
    debug = os.environ.get("FLASK_DEBUG", "false").lower() == "true"
    app.run(host="0.0.0.0", port=port, debug=debug)
