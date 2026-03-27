import asyncio
import os
import secrets
import threading
from datetime import datetime
from pathlib import Path

import telegram
from dotenv import load_dotenv
from flask import Flask, abort, request, jsonify

from agents import (
    run_inbox_agent,
    run_telegram_agent,
    notify_email,
    ALLOWED_CHAT_IDS,
    get_chat_id_for_user,
)
from tools.email import mail_client

load_dotenv()

app = Flask(__name__)

OBSIDIAN_VAULT = os.environ.get("OBSIDIAN_VAULT", "")
INBOX_API_KEY = os.environ.get("INBOX_API_KEY", "")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_WEBHOOK_URL = os.environ.get("TELEGRAM_WEBHOOK_URL", "")
TELEGRAM_WEBHOOK_SECRET = os.environ.get("TELEGRAM_WEBHOOK_SECRET")
if not TELEGRAM_WEBHOOK_SECRET:
    raise RuntimeError("TELEGRAM_WEBHOOK_SECRET environment variable is not set")
AGENTMAIL_WEBHOOK_URL = os.environ.get("AGENTMAIL_WEBHOOK_URL", "")


# ---------------------------------------------------------------------------
# Flask endpoints
# ---------------------------------------------------------------------------

@app.post("/telegram")
def telegram_webhook():
    token = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
    if token != TELEGRAM_WEBHOOK_SECRET:
        abort(403)

    data = request.get_json(silent=True) or {}
    message = data.get("message") or data.get("edited_message")
    if not message:
        return "", 200
    
    print(f"[telegram] received update: {data}")

    chat_id = str(message.get("chat", {}).get("id", ""))
    text = (message.get("text") or "").strip()

    if chat_id not in ALLOWED_CHAT_IDS:
        print(f"[telegram] ignored message from unauthorized chat_id: {chat_id}")
        return "", 200

    if not text:
        return "", 200

    print(f"[telegram] message from {chat_id}: {text}")
    threading.Thread(target=run_telegram_agent, args=(text, chat_id), daemon=True).start()
    return "", 200

# This is not related in email, this is an inbox for dictations or quick notes
@app.post("/inbox/<user>")
def inbox(user: str):
    api_key = request.headers.get("X-API-Key") or request.args.get("api_key")
    if not api_key or api_key != INBOX_API_KEY:
        abort(401)

    chat_id = get_chat_id_for_user(user)
    if chat_id is None:
        return jsonify({"error": f"unknown user: {user}"}), 404

    data = request.get_json(silent=True) or {}
    text = data.get("text", "").strip()
    if not text:
        return jsonify({"error": "text is required"}), 400

    # Also write to Inbox.md immediately as a safety net
    timestamp = datetime.now().strftime('%Y-%m-%dT%H:%M:%S')
    entry = f"[{timestamp}]: {text}"
    inbox_path = Path(OBSIDIAN_VAULT) / "Inbox.md"
    inbox_path.parent.mkdir(parents=True, exist_ok=True)
    with inbox_path.open("a") as f:
        f.write(f"\n{entry}")

    threading.Thread(target=run_inbox_agent, args=(text, chat_id), daemon=True).start()

    return jsonify({"ok": True}), 200


@app.post("/email")
def email_webhook():
    data = request.get_json(silent=True) or {}
    if data.get("event_type") != "message.received":
        return "", 200

    message = data.get("message", {})
    sender = message.get("from_", "")
    subject = message.get("subject", "")
    body = message.get("text") or message.get("extracted_text", "")
    thread_id = message.get("thread_id", "")
    message_id = message.get("message_id", "")

    print(f"[email] webhook received from: {sender} | subject: {subject} | thread: {thread_id}")
    threading.Thread(target=notify_email, args=(sender, subject, body, thread_id, message_id), daemon=True).start()
    return "", 200


def _register_telegram_webhook() -> None:
    if not TELEGRAM_BOT_TOKEN:
        return
    try:
        bot = telegram.Bot(token=TELEGRAM_BOT_TOKEN)
        asyncio.run(bot.set_webhook(url=TELEGRAM_WEBHOOK_URL, secret_token=TELEGRAM_WEBHOOK_SECRET))
        print(f"[telegram] webhook registered: {TELEGRAM_WEBHOOK_URL}")
    except Exception as e:
        print(f"[telegram] failed to register webhook: {e}")


def _register_agentmail_webhook() -> None:
    if not mail_client or not AGENTMAIL_WEBHOOK_URL:
        return
    try:
        mail_client.webhooks.create(
            url=AGENTMAIL_WEBHOOK_URL,
            event_types=["message.received"],
            client_id="todo-buddy-email-webhook",
        )
        print(f"[email] webhook registered: {AGENTMAIL_WEBHOOK_URL}")
    except Exception as e:
        print(f"[email] failed to register webhook: {e}")


_register_telegram_webhook()
_register_agentmail_webhook()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5055, debug=False)
