"""
MENTAL MODEL: Ink-2 streams the caller's words while they speak. Don't wait for turn.end.
Draft on every update, commit on end, discard on resume.
Jev is fast enough to re-guess on every new word, so it often knows where the call goes
before the caller has finished the sentence.
"""
import asyncio

from rich.console import Console

from lib.ink_replay import TURNS, replay
from lib.jev import IVR, ask_jev, build_menu_choice

CONFIDENCE_THRESHOLD = 0.95
TOP_MENU = build_menu_choice(IVR)
TOP_MENU.criteria["Not said yet"] = "The caller hasn't said what they need yet"  # mid-sentence, this is often true
console = Console()


async def pick_top_menu(transcript):
    response, ms = await ask_jev(transcript, {"pick": TOP_MENU})
    answer = response.choices["pick"]
    return answer.choice, answer.confidence, ms


async def draft(event, drafts, previous):
    pick, confidence, ms = await pick_top_menu(event["transcript"])
    drafts.append((event["t_ms"] + ms, pick, confidence))  # when the answer was ready
    if previous:
        await previous  # print rows in the order the words arrived
    console.print(f"{event['t_ms']:>6} | {event['type']:<14} | {event['transcript'][-40:]:<40} | {pick} ({confidence:.2f})")


async def listen(turn):
    console.rule(f"[bold]{turn['name']}")
    drafts, pending = [], []

    # 1. Ink-2 streams events. On every new partial transcript, Jev drafts a guess in the background.
    async for event in replay(turn):
        kind = event["type"]
        if kind in ("turn.update", "turn.eager_end"):
            pending.append(asyncio.create_task(draft(event, drafts, pending[-1] if pending else None)))
        # 2. The caller kept talking: throw away anything we'd started acting on.
        elif kind == "turn.resume":
            await asyncio.gather(*pending)  # let in-flight drafts print first, so the timeline reads in order
            console.print(f"{event['t_ms']:>6} | [yellow]{kind:<14} | discard draft[/]")
        elif kind == "turn.start":
            console.print(f"{event['t_ms']:>6} | {kind}")
    await asyncio.gather(*pending)

    # 3. turn.end: the old way asks Jev only now, on the final transcript.
    t_end, final = event["t_ms"], event["transcript"]
    final_pick, _, final_ms = await pick_top_menu(final)
    console.print(f"{t_end:>6} | [bold]turn.end[/]       | {final[-40:]:<40} | [bold]{final_pick}[/]")

    # 4. When did Jev first land on the final answer, confidently?
    t_knew = min((t for t, pick, conf in drafts if pick == final_pick and conf >= CONFIDENCE_THRESHOLD), default=None)
    wait_for_final = t_end + final_ms
    if t_knew is None:
        console.print(f"[red]Jev never got confident early. wait-for-final: {wait_for_final:.0f} ms[/]\n")
        return
    console.print(f"[bold green]JEV KNEW[/] at {t_knew:.0f} ms -> {final_pick}")
    console.print(
        f"wait-for-final: {wait_for_final:.0f} ms   vs   speculative: {t_knew:.0f} ms"
        f"   ->   [bold green]saved {wait_for_final - t_knew:.0f} ms[/]\n"
    )
    # 5. Commit: hand off to that department. The LLM and Sonic (TTS) around this don't change.


async def main():
    for turn in TURNS:
        await listen(turn)


asyncio.run(main())
