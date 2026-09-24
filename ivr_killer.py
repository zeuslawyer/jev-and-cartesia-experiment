"""
MENTAL MODEL: The old way, an IVR system makes the caller listen to menus and press buttons to reach a team.
The new way, the caller says one sentence and Jev picks the team directly, with a confidence score.
Jev never sees the IVR menus, only the list of teams.
The same request also asks one yes/no question: is this caller upset enough to need a human now?
"""
import asyncio
import sys

from rich.console import Console
from rich.tree import Tree
from typesafe_sdk import Choice, Noul

from lib.jev import IVR, ask

CONFIDENCE_THRESHOLD = 0.95
SECONDS_PER_OPTION = 3  # how long an IVR system takes to read out one option
HUMAN_TEAM = "General reservations agent"

# Each example: what the caller said, and the buttons a person would press in the IVR system.
EXAMPLES = [
    ("hi yeah my bag didn't come off the carousel in denver and nobody can find it", [4, 1]),
    ("um i need to sort something out with my flight", [3]),
    ("i don't wanna cancel, i just need to move it to friday instead", [3, 2, 1]),
    ("not a refund, no, i want the points from my last flight, they never showed up", [5, 1]),
    ("this is the third time you people lost my bag, i'm absolutely fed up, i want to talk to a human right now", [6]),
]
ESCALATE = Noul(
    instructions="Is the caller agitated or frustrated enough that the call must go to a human next?",
    criteria={
        "true": "The caller is angry, frustrated or demanding a person; an automated menu would make it worse",
        "false": "The caller is calm, impatient or only mildly annoyed; the automated menu is fine",
    },
)
console = Console()


def list_teams(menu):
    """Every team at the bottom of the IVR tree (the leaf nodes), with what callers want from it:
    the description of the menu option just above it. A team can appear in more than one place."""
    for option in menu["options"]:
        if "options" in option:
            yield from list_teams(option)
        else:
            yield option["label"], menu["description"]


TEAM_DESCRIPTIONS = {}
for label, description in list_teams(IVR):
    TEAM_DESCRIPTIONS.setdefault(label, []).append(description)
PICK_TEAM = Choice(
    instructions="Skyline Air phone line. Which team should handle what the caller wants?",
    criteria={label: "; ".join(descriptions) for label, descriptions in TEAM_DESCRIPTIONS.items()},
)


def build_ivr_tree(menu, buttons, branch):
    """Draw the IVR under `branch`, with option numbers. `buttons` is the list of numbers still to press;
    the path they lead to prints in bold green. None = this branch is off the path."""
    for number, option in enumerate(menu.get("options", []), 1):
        is_team = "options" not in option
        on_path = buttons is not None and (buttons[:1] == [number] or (not buttons and is_team))
        text = f"-> {option['label']}" if is_team else f"{number} {option['label']}"
        child = branch.add(f"[bold green]{text}[/]" if on_path else f"[dim]{text}[/]")
        build_ivr_tree(option, buttons[1:] if buttons is not None and on_path else None, child)
    return branch


def show_old_way(buttons):
    """The IVR system: the full menu tree, the path a person presses, and how long they listen."""
    console.print("[red]Old way, IVR system:[/] the caller listens to the menus and presses buttons")
    console.print(build_ivr_tree(IVR, buttons, Tree(IVR["label"])))

    menu, options_heard = IVR, 0

    for number in buttons:
        options_heard += len(menu["options"])
        menu = menu["options"][number - 1]
    console.print(f"\n[red]Old way, IVR system:[/] {len(buttons)} menus heard, ~{options_heard * SECONDS_PER_OPTION}s of listening\n")


async def show_new_way(transcript):
    """Jev: one request, two questions answered in parallel. Which team, and does the caller need a human?"""
    response, ms = await ask(transcript, {"team": PICK_TEAM, "escalate": ESCALATE})
    is_upset = response.nouls["escalate"].noul
    answer = response.choices["team"]
    console.print(f"[magenta]needs a human?[/] {is_upset:.2f}")
    console.print(f"[yellow]Jev chose: [bold]{answer.choice}[/] | confidence: {answer.confidence:.2f} | latency {ms:.0f} ms")
    console.print(f'[cyan]New way, Jev:[/] the caller says one sentence: "{transcript}"\n and spent ~{ms/1000} seconds to find the right team' )


    # Upset caller? Skip everything and hand them to a person.
    if is_upset >= CONFIDENCE_THRESHOLD:
        console.print(f"[bold magenta]-> escalating straight to a human[/]")
        console.print(f"[green]Transfer to: {HUMAN_TEAM}[/]  (Sonic would say: \"Connecting you now.\")\n")
    # Not sure? Ask one short question between the top two teams. No LLM.
    elif answer.confidence < CONFIDENCE_THRESHOLD:
        first, second = sorted(answer.probabilities, key=lambda team: answer.probabilities[team], reverse=True)[:2]
        console.print(
            f'    >>>> [yellow]Jev confidence below {CONFIDENCE_THRESHOLD}.[/] Agent asks: "Is this for {first} or {second}?"\n'
        )
    else:
        console.print(f"\n[green]Transfer to: {answer.choice}[/]  (Sonic would say: \"Connecting you now.\")\n")


async def main():
    """Run every example, or pass example indexes (from 0) to run only those, e.g. `uv run ivr_killer.py 1`."""
    numbers = [int(arg) for arg in sys.argv[1:]] or range(len(EXAMPLES))
    for number in numbers:
        transcript, buttons = EXAMPLES[number]
        console.rule(title=f"============== EXAMPLE {number} ==============")
        # Cartesia Ink-2 (speech-to-text) hands us what the caller said. No audio here: it's text.
        console.print(f'[cyan]User (Cartesia Ink-2 transcription):[/] "{transcript}"\n')
        show_old_way(buttons)
        await show_new_way(transcript)


asyncio.run(main())
