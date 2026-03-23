import asyncio
import json
import os
import threading
import urllib.request
from datetime import datetime
from pathlib import Path

import telegram
from agentmail import AgentMail
from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain.chat_models import init_chat_model
from langchain.tools import tool

load_dotenv()

OBSIDIAN_VAULT = os.environ.get("OBSIDIAN_VAULT", "")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")
TELEGRAM_CHAT_ID_2 = os.environ.get("TELEGRAM_CHAT_ID_2", "")
GITHUB_PAT = os.environ.get("GITHUB_PAT", "")
SOUL_URL = os.environ.get("SOUL_URL", "")
CONFIG_FILE_URL = os.environ.get("CONFIG_FILE_URL", "")
AGENTMAIL_API_KEY = os.environ.get("AGENTMAIL_API_KEY", "")
AGENTMAIL_INBOX_ID = os.environ.get("AGENTMAIL_INBOX_ID", "")

mail_client = AgentMail(api_key=AGENTMAIL_API_KEY) if AGENTMAIL_API_KEY else None


def _load_config() -> dict:
    """Load config from a local file (file://) or private GitHub repo."""
    if CONFIG_FILE_URL.startswith("file://"):
        local = Path(CONFIG_FILE_URL[7:])
        print(f"[config] Trying local file: {local}")
        if local.exists():
            data = json.loads(local.read_text())
            print(f"[config] Loaded successfully from local file ({len(data)} keys)")
            return data
        print(f"[config] Local file not found: {local}")
        return {}

    if CONFIG_FILE_URL and GITHUB_PAT:
        url = f"https://raw.githubusercontent.com/{CONFIG_FILE_URL}"
        print(f"[config] Trying GitHub URL: {url}")
        print(f"[config] Trying GitHub URL: {url}")
        req = urllib.request.Request(url, headers={"Authorization": f"token {GITHUB_PAT}"})
        try:
            with urllib.request.urlopen(req) as resp:
                data = json.loads(resp.read().decode())
                print(f"[config] Loaded successfully from GitHub ({len(data)} keys)")
                return data
        except Exception as e:
            print(f"[config] Failed to fetch from GitHub: {e}")
    else:
        print(f"[config] No CONFIG_FILE_URL or GITHUB_PAT set, skipping")

    return {}


def _fetch_text_from_url(url: str, label: str = "file") -> str:
    """Load text content from a local file (file://) or private GitHub repo path."""
    if not url:
        return ""

    if url.startswith("file://"):
        local = Path(url[7:])
        print(f"[{label}] Trying local file: {local}")
        if local.exists():
            content = local.read_text().strip()
            print(f"[{label}] Loaded successfully from local file ({len(content)} chars)")
            return content
        print(f"[{label}] Local file not found: {local}")
        return ""

    if GITHUB_PAT:
        gh_url = f"https://raw.githubusercontent.com/{url}"
        print(f"[{label}] Trying GitHub URL: {gh_url}")
        req = urllib.request.Request(gh_url, headers={"Authorization": f"token {GITHUB_PAT}"})
        try:
            with urllib.request.urlopen(req) as resp:
                content = resp.read().decode().strip()
                print(f"[{label}] Loaded successfully from GitHub ({len(content)} chars)")
                return content
        except Exception as e:
            print(f"[{label}] Failed to fetch from GitHub: {e}")
    else:
        print(f"[{label}] No GITHUB_PAT set, skipping")

    return ""


def _load_system_prompt_suffix() -> str:
    """Load additional system prompt content from SOUL_URL (legacy global soul)."""
    content = _fetch_text_from_url(SOUL_URL, label="soul")
    return ("\n\n" + content) if content else ""


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------

@tool
def list_vault_files() -> str:
    """List all markdown files currently in the Obsidian vault.
    Returns a newline-separated list of relative paths (e.g. 'ToDos/Grocery.md', 'Trips/Paris Trip 2026-05.md').
    Use this to discover existing lists before deciding where to file an item."""
    vault = Path(OBSIDIAN_VAULT)
    files = sorted(
        str(p.relative_to(vault))
        for p in vault.glob("**/*.md")
        if p.name != "Inbox.md"
    )
    return "\n".join(files) if files else "(no files yet)"


@tool
def read_file(filename: str) -> str:
    """Read the contents of a markdown file in the Obsidian vault.
    Use this to answer questions like 'what's on my grocery list?' or 'what are my house projects?'.
    Args:
        filename: Relative path within the vault (e.g. 'ToDos/Grocery.md'). Must end with .md.
    """
    if not filename.endswith(".md"):
        filename = filename + ".md"
    path = Path(OBSIDIAN_VAULT) / filename
    if not path.exists():
        return f"{filename} does not exist."
    return path.read_text()


@tool
def add_todo(filename: str, text: str) -> str:
    """Append a timestamped todo bullet entry to a markdown file under the ToDos/ folder.
    If the file does not exist it will be created with a heading derived from the filename.
    Args:
        filename: The .md filename (e.g. 'Grocery.md'). Do NOT include the 'ToDos/' prefix — it is added automatically.
        text: The todo item text to append (without timestamp — that is added automatically).
    """
    if not filename.endswith(".md"):
        filename = filename + ".md"
    # Strip any leading path the model may accidentally include, then place under ToDos/
    filename = Path(filename).name
    path = Path(OBSIDIAN_VAULT) / "ToDos" / filename
    path.parent.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y-%m-%d")
    entry = f"\n- [ ] {text} ({timestamp})"

    if not path.exists():
        heading = path.stem.replace("_", " ").replace("-", " ").title()
        path.write_text(f"# {heading}\n")

    with path.open("a") as f:
        f.write(entry)

    return f"Appended to ToDos/{filename}."


@tool
def write_trip_file(filename: str, content: str) -> str:
    """Write or update a trip planning file under the Trips/ folder in the Obsidian vault.
    Use this for flight bookings, hotel reservations, itineraries, and other trip details.
    Unlike add_todo, this writes free-form markdown content (not a todo bullet).
    If the file already exists, the content is appended. If not, it is created.
    Args:
        filename: The .md filename using the DESTINATION city (where they fly TO), NOT the origin/departure city.
            e.g. flight from Seattle to Sacramento → 'Sacramento Trip 2026-05.md' (NEVER 'Seattle Trip 2026-05.md')
            Do NOT include the 'Trips/' prefix — it is added automatically.
        content: The full markdown content to write (structured trip details).
    """
    if not filename.endswith(".md"):
        filename = filename + ".md"
    filename = Path(filename).name
    path = Path(OBSIDIAN_VAULT) / "Trips" / filename
    path.parent.mkdir(parents=True, exist_ok=True)

    if path.exists():
        with path.open("a") as f:
            f.write(f"\n\n{content.strip()}")
    else:
        path.write_text(content.strip())

    return f"Trip file written: Trips/{filename}."


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


# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

_PROMPTS_DIR = Path(__file__).parent / "prompts"


def _load_prompt(filename: str) -> str:
    return (_PROMPTS_DIR / filename).read_text().strip()


INBOX_SYSTEM_PROMPT = _load_prompt("inbox.md")
_TELEGRAM_BASE_PROMPT = _load_prompt("telegram.md")
EMAIL_TRIAGE_PROMPT = _load_prompt("email_triage.md")


# ---------------------------------------------------------------------------
# Agent setup
# ---------------------------------------------------------------------------

TELEGRAM_HISTORY_LIMIT = 20

_model = init_chat_model("claude-sonnet-4-6", temperature=0)

inbox_agent = create_agent(
    model=_model,
    system_prompt=INBOX_SYSTEM_PROMPT,
    tools=[list_vault_files, add_todo],
)

_telegram_histories: dict[str, list[dict]] = {}
_telegram_history_lock = threading.Lock()

_config = _load_config()

# Build per-user agents from config["users"] 
_users: dict[str, dict] = {}

if "users" in _config:
    for name, info in _config["users"].items():
        cid = str(info["telegram_chat_id"])
        _users[cid] = {"name": name, "soul_url": info.get("soul_url", "")}

# Build ALLOWED_CHAT_IDS from telegram_chat_id values in users
ALLOWED_CHAT_IDS: set[str] = set(str(info["telegram_chat_id"]) for info in _config["users"].values())



def _build_telegram_agent(chat_id: str):
    user = _users.get(chat_id, {})
    name = user.get("name", chat_id)
    soul_url = user.get("soul_url", "")
    soul = _fetch_text_from_url(soul_url, label=f"soul:{name}") if soul_url else _load_system_prompt_suffix()
    suffix = ("\n\n" + soul) if soul else ""
    system_prompt = f"You are talking to {name}.\n\n" + _TELEGRAM_BASE_PROMPT + suffix
    return create_agent(
        model=_model,
        system_prompt=system_prompt,
        tools=[list_vault_files, read_file, add_todo, write_trip_file, send_email],
    )


_telegram_agents: dict[str, object] = {
    chat_id: _build_telegram_agent(chat_id) for chat_id in _users
}

_pending_emails: dict[str, dict] = {}
_pending_email_counter = 0
_pending_emails_lock = threading.Lock()

_email_triage_agent = None


def _get_email_triage_agent():
    global _email_triage_agent
    if _email_triage_agent is None:
        _email_triage_agent = create_agent(
            model=init_chat_model("claude-haiku-4-5-20251001", temperature=0),
            system_prompt=EMAIL_TRIAGE_PROMPT,
            tools=[list_vault_files, add_todo, write_trip_file],
        )
    return _email_triage_agent


# ---------------------------------------------------------------------------
# Agent runners
# ---------------------------------------------------------------------------

def _log_usage_and_reply(result: dict, label: str) -> str:
    reply = result["messages"][-1].content
    usage = getattr(result["messages"][-1], "usage_metadata", None)
    if usage:
        print(f"[{label}] tokens — input: {usage.get('input_tokens', '?')}, output: {usage.get('output_tokens', '?')}, total: {usage.get('total_tokens', '?')}")
    print(f"[{label}] response: {reply}")
    return reply


async def _send_telegram(chat_id: str, text: str) -> None:
    bot = telegram.Bot(token=TELEGRAM_BOT_TOKEN)
    await bot.send_message(chat_id=chat_id, text=text)


def _store_pending_email(thread_id: str, message_id: str, sender: str, subject: str) -> str:
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


def _get_telegram_messages(chat_id: str, new_text: str) -> list[dict]:
    with _telegram_history_lock:
        history = _telegram_histories.get(chat_id, [])[-TELEGRAM_HISTORY_LIMIT:]
        return history + [{"role": "user", "content": new_text}]


def _append_telegram_history(chat_id: str, user_text: str, assistant_reply: str) -> None:
    with _telegram_history_lock:
        hist = _telegram_histories.setdefault(chat_id, [])
        hist.append({"role": "user", "content": user_text})
        hist.append({"role": "assistant", "content": assistant_reply})


def get_chat_id_for_user(username: str) -> str | None:
    """Return the telegram_chat_id for a user by name (case-insensitive), or None if not found."""
    lower = username.lower()
    for chat_id, info in _users.items():
        if info["name"].lower() == lower:
            return chat_id
    return None


def run_inbox_agent(text: str, chat_id: str | None = None) -> None:
    print(f"[inbox] input: {text}")
    try:
        result = inbox_agent.invoke({"messages": [{"role": "user", "content": text}]})
        reply = _log_usage_and_reply(result, "inbox")
        target = chat_id or TELEGRAM_CHAT_ID
        if TELEGRAM_BOT_TOKEN and target:
            asyncio.run(_send_telegram(target, reply))
    except Exception as e:
        print(f"[inbox error] {e}")


def run_telegram_agent(text: str, chat_id: str) -> None:
    print(f"[telegram] input: {text}")
    try:
        messages = _get_telegram_messages(chat_id, text)
        result = _telegram_agents[chat_id].invoke({"messages": messages})
        reply = _log_usage_and_reply(result, "telegram")
        _append_telegram_history(chat_id, text, reply)
        asyncio.run(_send_telegram(chat_id, reply))
    except Exception as e:
        print(f"[telegram error] {e}")


def _fetch_thread_body(thread_id: str) -> str:
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


def notify_email(sender: str, subject: str, body: str, thread_id: str, message_id: str) -> None:
    print(f"[email] received from: {sender} | subject: {subject}")
    try:
        if not body.strip() and thread_id:
            print(f"[email] body empty, fetching thread {thread_id}")
            body = _fetch_thread_body(thread_id)

        prompt = f"From: {sender}\nSubject: {subject}\n\nBody:\n{body[:4000]}"
        result = _get_email_triage_agent().invoke({"messages": [{"role": "user", "content": prompt}]})
        reply = result["messages"][-1].content.strip()

        if not reply or reply.upper() == "SKIP":
            print(f"[email] skipped marketing email from {sender}")
            return

        ref = _store_pending_email(thread_id, message_id, sender, subject)
        notification = f"{reply}\n[ref: {ref}]"
        if TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID:
            asyncio.run(_send_telegram(TELEGRAM_CHAT_ID, notification))
    except Exception as e:
        print(f"[email notify error] {e}")
