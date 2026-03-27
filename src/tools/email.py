import os
import threading

from agentmail import AgentMail
from dotenv import load_dotenv
from langchain.tools import tool

load_dotenv()

AGENTMAIL_API_KEY = os.environ.get("AGENTMAIL_API_KEY", "")
AGENTMAIL_INBOX_ID = os.environ.get("AGENTMAIL_INBOX_ID", "")

mail_client = AgentMail(api_key=AGENTMAIL_API_KEY) if AGENTMAIL_API_KEY else None

_pending_emails: dict[str, dict] = {}
_pending_email_counter = 0
_pending_emails_lock = threading.Lock()


@tool
def send_email(to: str, subject: str, body: str) -> str:
    """Send an email on behalf of the user.
    Args:
        to: Recipient email address.
        subject: Email subject line.
        body: Plain text email body.
    """
    if not mail_client:
        return "Email is not configured."
    try:
        mail_client.inboxes.messages.send(
            AGENTMAIL_INBOX_ID,
            to=to,
            subject=subject,
            text=body,
        )
        print(f"[email] to: {to} | subject: {subject}\n{body}")
        return f"Email sent to {to}."
    except Exception as e:
        return f"Failed to send email: {e}"


def store_pending_email(thread_id: str, message_id: str, sender: str, subject: str) -> str:
    global _pending_email_counter
    with _pending_emails_lock:
        _pending_email_counter += 1
        ref = str(_pending_email_counter)
        _pending_emails[ref] = {
            "thread_id": thread_id,
            "message_id": message_id,
            "sender": sender,
            "subject": subject,
        }
    return ref


def get_pending_email(ref: str) -> dict | None:
    with _pending_emails_lock:
        return _pending_emails.get(ref)


def fetch_thread_body(thread_id: str) -> str:
    """Fetch full thread content from AgentMail when the webhook body is empty."""
    if not mail_client or not thread_id:
        return ""
    try:
        thread = mail_client.threads.get(thread_id)
        parts = []
        for msg in thread.messages:
            text = getattr(msg, "extracted_text", None) or getattr(msg, "text", None) or ""
            if text:
                parts.append(text.strip())
        return "\n\n---\n\n".join(parts)
    except Exception as e:
        print(f"[email] failed to fetch thread {thread_id}: {e}")
        return ""
