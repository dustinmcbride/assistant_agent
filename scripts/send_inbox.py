#!/usr/bin/env python3
"""Send a to-do item to the local todo_buddy server."""

import os
import sys
import json
import random
import urllib.request
import urllib.error
from pathlib import Path

CHORES = [
    "Clean out the fridge",
    "Wipe down kitchen cabinets",
    "Replace HVAC filter",
    "Unclog bathroom drain",
    "Reseal grout in the shower",
    "Organize the garage",
    "Clean out gutters",
    "Dust ceiling fan blades",
    "Deep clean the oven",
    "Vacuum behind the couch",
    "Clean window tracks",
    "Replace smoke detector batteries",
    "Oil squeaky door hinges",
    "Declutter the junk drawer",
    "Wash all the bed linens",
    "Power wash the driveway",
    "Touch up paint scuffs on walls",
    "Tighten loose cabinet handles",
    "Clean out under the bathroom sink",
    "Wipe down light switches and doorknobs",
    "Sort and donate old clothes",
    "Clean the dryer lint trap and vent",
    "Mop the floors",
    "Organize the pantry",
    "Fix that running toilet",
]

LIFE_ADMIN = [
    "File last year's taxes",
    "Review monthly subscriptions and cancel unused ones",
    "Update passwords in password manager",
    "Schedule dentist appointment",
    "Review health insurance plan",
    "Update emergency contacts",
    "Back up phone photos to cloud",
    "Shred old financial documents",
    "Check credit report",
    "Update resume",
    "Review and update beneficiaries on accounts",
    "Schedule annual physical",
    "Call about that insurance claim",
    "Organize digital files and folders",
    "Set up automatic bill pay",
    "Review car insurance policy",
    "Renew driver's license",
    "Register to vote / check registration",
    "Review and rebalance investment accounts",
    "Clean up email inbox",
    "Make a will or review existing one",
    "Check if passport needs renewal",
    "Set up a budget for next month",
    "Cancel that gym membership you never use",
    "Research home warranty options",
]

GROCERIES = [
    "Olive oil",
    "Greek yogurt",
    "Sourdough bread",
    "Eggs (2 dozen)",
    "Chicken thighs",
    "Lemons",
    "Garlic",
    "Fresh ginger",
    "Butter (unsalted)",
    "Heavy cream",
    "Parmesan block",
    "Canned tomatoes",
    "Dry pasta — rigatoni",
    "Brown rice",
    "Coconut milk",
    "Kimchi",
    "Miso paste",
    "Soy sauce",
    "Sriracha",
    "Pine nuts",
    "Fresh herbs — thyme, rosemary",
    "Baby spinach",
    "Cherry tomatoes",
    "Avocados x4",
    "Sparkling water (case)",
]

RANDOM_THOUGHTS = [
    "Look up how to sharpen kitchen knives properly",
    "Research that weird noise the car makes",
    "Find a good podcast for the commute",
    "Look into learning a new programming language",
    "Write down 3 things you're grateful for",
    "Send that long overdue text to an old friend",
    "Research sauna protocols for recovery",
    "Look into local hiking trails",
    "Find a good audiobook for the next ski trip",
    "Try making homemade pasta",
    "Research gut health supplements",
    "Plan a weekend trip somewhere new",
    "Start that side project you keep putting off",
    "Read that article you bookmarked 3 months ago",
    "Learn one new keyboard shortcut today",
    "Watch a documentary about something you know nothing about",
    "Call mom or dad just to chat",
    "Take a walk without your phone",
    "Write down ideas for the backyard project",
    "Look up a new recipe to try this week",
    "Spend 15 minutes stretching",
    "Unsubscribe from 5 mailing lists",
    "Figure out what you actually want for dinner",
    "Sit outside for 10 minutes and do nothing",
    "Think about what you want this year to look like",
]


def _load_env() -> None:
    env_path = Path(__file__).parent.parent / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip())


_load_env()

HOST = os.environ.get("INBOX_HOST", "http://localhost:5055")
API_KEY = os.environ.get("INBOX_API_KEY", "")



LISTS = {
    "--chore": CHORES,
    "--grocery": GROCERIES,
    "--admin": LIFE_ADMIN,
    "--thought": RANDOM_THOUGHTS,
}


def main() -> None:
    if len(sys.argv) >= 2 and sys.argv[1] in LISTS:
        lst = LISTS[sys.argv[1]]
        text = random.choice(lst)
        print(f"Random ({sys.argv[1]}): {text}")
    elif len(sys.argv) < 2:
        text = random.choice(CHORES + GROCERIES + LIFE_ADMIN + RANDOM_THOUGHTS)
        print(f"Random: {text}")
    else:
        text = " ".join(sys.argv[1:])
    payload = json.dumps({"text": text}).encode()

    req = urllib.request.Request(
        f"{HOST}/inbox",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "X-API-Key": API_KEY,
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req) as resp:
            body = json.loads(resp.read())
            print(f"ok: {body}")
    except urllib.error.HTTPError as e:
        print(f"error {e.code}: {e.read().decode()}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
