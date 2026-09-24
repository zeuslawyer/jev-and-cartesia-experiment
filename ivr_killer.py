"""
MENTAL MODEL: An IVR system makes the caller listen to every menu and press buttons.
With Jev, the caller says one sentence and Jev picks the whole button sequence at once,
from one list of every route through the IVR, with a confidence score.
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
AGENT_ROUTE = "6"  # buttons for "Speak to an agent"

EXAMPLES = [
    "hi yeah my bag didn't come off the carousel in denver and nobody can find it",
    "um i need to sort something out with my flight",
    "i don't wanna cancel, i just need to move it to friday instead",
    "not a refund, no, i want the points from my last flight, they never showed up",
    "this is the third time you people lost my bag, i'm absolutely fed up, i want to talk to a human right now",
]
ESCALATE = Noul(
    instructions="Is the caller agitated or frustrated enough that the call must go to a human next?",
    criteria={
        "true": "The caller is angry, frustrated or demanding a person; an automated menu would make it worse",
        "false": "The caller is calm, impatient or only mildly annoyed; the automated menu is fine",
    },
)
console = Console()


def list_routes(menu, buttons="", labels=""):
    """Flatten the IVR into every route a caller can end on.
    Yields (buttons, labels, description, team), e.g. ("4-1", "Baggage > Lost bag", "Your bag never arrived...", "Baggage claims team").
    Buttons are option numbers, counted from 1 in the order the IVR reads them out."""
    for number, option in enumerate(menu["options"], 1):
        if "options" in option:
            yield from list_routes(option, f"{buttons}-{number}".lstrip("-"), f"{labels} > {option['label']}".lstrip(" >"))
        else:
            yield buttons, labels, menu["description"], option["label"]


ROUTES = {buttons: (labels, team) for buttons, labels, _, team in list_routes(IVR)}
PICK_ROUTE = Choice(
    instructions="Skyline Air phone line. Which route through the phone menu matches what the caller wants?",
    criteria={buttons: f"{labels}: {description}" for buttons, labels, description, _ in list_routes(IVR)},
)


def build_ivr_tree(menu, buttons, branch):
    """Draw the IVR under `branch`. `buttons` is the list of option numbers still to press; the chosen path prints in bold green."""
    for number, option in enumerate(menu.get("options", []), 1):
        on_path = buttons is not None and (buttons[:1] == [number] or not buttons)
        text = f"{number} {option['label']}" if "options" in option else f"-> {option['label']}"
        child = branch.add(f"[bold green]{text}[/]" if on_path else f"[dim]{text}[/]")
        build_ivr_tree(option, buttons[1:] if buttons is not None and on_path else None, child)
    return branch


async def route_call(transcript):
    # 1. Cartesia Ink-2 (speech-to-text) hands us what the caller said. No audio here: it's text.
    console.print("[red]IVR System:[/] Hi there, welcome to Skyline Air.  How can I help you?")
    console.print(f'[cyan]Cartesia Ink-2 transcription:[/] "{transcript}"\n')

    # 2. One request to Jev: which route, and does the caller need a human? Both answered in parallel.
    response, ms = await ask(transcript, {"route": PICK_ROUTE, "escalate": ESCALATE})
    is_upset = response.nouls["escalate"].noul
    answer = response.choices["route"]
    console.print(f"[magenta]needs a human?[/] {is_upset:.2f}")
    console.print(f"[yellow]Jev chose: {answer.choice} ({ROUTES[answer.choice][0]}) | confidence: {answer.confidence:.2f} | latency {ms:.0f} ms")

    # 3. Upset caller? Skip the menus and hand them to a person.
    route = answer.choice
    if is_upset >= CONFIDENCE_THRESHOLD:
        console.print("[bold magenta]-> escalating straight to a human[/]")
        route = AGENT_ROUTE

    # 4. Not sure? Ask one short question between the top two routes. No LLM.
    elif answer.confidence < CONFIDENCE_THRESHOLD:
        first, second = sorted(answer.probabilities, key=lambda route: answer.probabilities[route], reverse=True)[:2]
        console.print(
            f'    >>>> [yellow]Jev confidence below {CONFIDENCE_THRESHOLD}.[/] [red]IVR System:[/] asks: '
            f"\"Is this about '{ROUTES[first][0]}' or '{ROUTES[second][0]}'?\"\n"
        )
        return

    # 5. Show the path through the full IVR, then compare with pressing buttons.
    buttons = [int(number) for number in route.split("-")]
    console.print("\n\nHere's the path through the IVR tree:")
    console.print(build_ivr_tree(IVR, buttons, Tree(IVR["label"])))
    console.print(f"[green]Transfer to: {ROUTES[route][1]}[/]  (Sonic would say: \"Connecting you now.\")")
    menu, options_heard = IVR, 0
    for number in buttons:
        options_heard += len(menu["options"])
        menu = menu["options"][number - 1]
    console.print(
        f"IVR system: {len(buttons)} menus heard, ~{options_heard * SECONDS_PER_OPTION}s of listening"
        f"   vs   Jev: 1 sentence spoken, response in {ms:.0f} ms\n"
    )


async def main():
    for idx, transcript in enumerate(sys.argv[1:] or EXAMPLES):
        console.rule(title=f"============== EXAMPLE {idx+1}==============")
        await route_call(transcript)


asyncio.run(main())
