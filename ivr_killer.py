"""
MENTAL MODEL: Touch-tone makes the caller listen to every menu and press buttons.
With Jev, the caller says one sentence and Jev presses the buttons for them:
one small Choice per menu, each with a confidence score.
The same request also asks one yes/no question: is this caller upset enough to need a human now?
"""
import asyncio
import enum
import sys

from rich.console import Console
from rich.tree import Tree
from typesafe_sdk import Noul

from lib.jev import IVR, ask, build_menu_choice

CONFIDENCE_THRESHOLD = 0.95
SECONDS_PER_OPTION = 3  # how long a touch-tone system takes to read out one option

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
HUMAN = next(option for option in IVR["options"] if option["label"] == "Speak to an agent")
console = Console()


def build_ivr_tree(node, chosen, tree=None):
    """Draw the whole IVR, with the nodes Jev chose in bold green."""
    label = f"[bold green]{node['label']}[/]" if id(node) in chosen else f"[dim]{node['label']}[/]"
    branch = tree.add(label) if tree else Tree(label)
    for option in node.get("options", []):
        build_ivr_tree(option, chosen, branch)
    return branch


async def route_call(transcript):
    # 1. Cartesia Ink-2 (speech-to-text) hands us what the caller said. No audio here: it's text.
    console.print(f'[red]IVR System:[/] Hi there, welcome to Skyline Air.  How can I help you?')
    console.print(f'[cyan]Cartesia Ink-2 transcription:[/] "{transcript}"\n')

    # 2. Walk down the menus. At each one, Jev picks the button.
    menu, chosen, menus_heard, options_heard, total_ms = IVR, {id(IVR)}, 0, 0, 0

    while menu.get("options"):
        options = menu["options"]
        if len(options) == 1:  # one option = just the transfer to that team, no question needed
            menu = options[0]
            chosen.add(id(menu))
            continue

        menus_heard += 1
        options_heard += len(options)
        
        questions = {"pick": build_menu_choice(menu)}
        if menu is IVR:
            questions["escalate"] = ESCALATE  # asked in parallel, same request
        
        response, ms = await ask(transcript, questions)
        
        total_ms += ms

        # 3. Upset caller? Skip the menus and hand them to a person.
        if menu is IVR:
            is_upset = response.nouls["escalate"].noul
            console.print(f"[magenta]needs a human?[/] {is_upset:.2f}")
            if is_upset >= CONFIDENCE_THRESHOLD:
                console.print("[bold magenta]-> escalating straight to a human[/]")
                menu = HUMAN
                chosen.add(id(menu))
                continue
        
        # Else, caller not upset        
        answer = response.choices["pick"]
        console.print(f"[yellow]Jev Chose: {menu['label']} -> [bold]{answer.choice}[/] | confidence: {answer.confidence:.2f} Latency {ms:.0f} ms")

        # 4. Not sure? Ask one short question about this menu only. No LLM.
        if answer.confidence < CONFIDENCE_THRESHOLD:
            first, second = sorted(answer.probabilities, key=answer.probabilities.get, reverse=True)[:2]
            console.print(f'    >>>> [yellow]Jev Confidence below {CONFIDENCE_THRESHOLD}.[/] [red]IVR System:[/] asks: "Is this about \'{first}\' or \'{second}\'?"')
            break
        menu = next(option for option in options if option["label"] == answer.choice)
        chosen.add(id(menu))

    # 5. Show the path through the full IVR, then compare with touch-tone.
    console.print("\n\nHere's the path through the IVR tree:")
    console.print(build_ivr_tree(IVR, chosen))
    if not menu.get("options"):
        console.print(f"[green]Transfer to: {menu['label']}[/]  (Sonic would say: \"Connecting you now.\")")
    console.print(
        f"touch-tone: {menus_heard} menus heard, ~{options_heard * SECONDS_PER_OPTION}s of listening"
        f"   vs   Jev: 1 sentence spoken, response in {total_ms:.0f} ms\n"
    )


async def main():
    for idx, transcript in enumerate(sys.argv[1:] or EXAMPLES):
        console.rule(title=f'============== EXAMPLE {idx+1}==============')
        await route_call(transcript)


asyncio.run(main())
