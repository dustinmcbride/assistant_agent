import os

from dotenv import load_dotenv
from langchain.tools import tool
from trello import TrelloClient

load_dotenv()

TRELLO_API_KEY = os.environ.get("TRELLO_API_KEY", "")
TRELLO_TOKEN = os.environ.get("TRELLO_TOKEN", "")


@tool
def get_cards_by_list(list_id: str) -> str:
    """Get all cards in a Trello list, returning only the name, description, and completion status.
    Use this to check for duplicates before adding a new card.
    Args:
        list_id: The Trello list ID (available from the Trello Boards & Lists context).
    """
    if not TRELLO_API_KEY or not TRELLO_TOKEN:
        return "Trello is not configured."
    try:
        client = TrelloClient(api_key=TRELLO_API_KEY, token=TRELLO_TOKEN)
        lst = client.get_list(list_id)
        cards = lst.list_cards()
        if not cards:
            return "(no cards)"
        lines = []
        for card in cards:
            status = "done" if card.closed else "open"
            desc = f" — {card.description.strip()}" if card.description and card.description.strip() else ""
            lines.append(f"- [{status}] {card.name}{desc}")
        return "\n".join(lines)
    except Exception as e:
        return f"Failed to fetch cards: {e}"
