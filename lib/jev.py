import json
import time

from dotenv import load_dotenv
from typesafe_sdk import AsyncTypeSafeClient, Choice

load_dotenv()
client = AsyncTypeSafeClient(model="jev-1.13.0")
IVR = json.load(open("data/airline_ivr.json"))


def build_menu_choice(menu):
    """One phone menu -> one Jev Choice. Each option's label is the answer; its description is the rubric."""
    return Choice(
        instructions=f"The caller is at the '{menu['label']}' phone menu. Which option matches what the caller wants?",
        criteria={option["label"]: option["description"] for option in menu["options"]},
    )


async def ask(state, questions):
    """Send one request to Jev. Returns (answers, milliseconds it took)."""
    start = time.perf_counter()
    response = await client.system_one(state=state, questions=questions)
    return response, (time.perf_counter() - start) * 1000
