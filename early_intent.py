"""
MENTAL MODEL: Ink-2 streams the caller's words while they speak. Don't wait for turn.end.
Guess on every update, commit on end, cancel on resume.
Jev is fast enough to re-guess on every new word, so it often knows where the call goes
before the caller has finished the sentence.
"""
import asyncio

from rich.console import Console

from lib.ink_replay import TURNS, replay_turn_events
from lib.jev import IVR, ask_jev, build_menu_choice

CONFIDENCE_THRESHOLD = 0.95
DEPARTMENT_QUESTION = build_menu_choice(IVR)
DEPARTMENT_QUESTION.criteria["Not said yet"] = "The caller hasn't said what they need yet"  # mid-sentence, this is often true
console = Console()


async def guess_department(transcript):
    """Ask Jev which department the caller needs, from the words so far.
    transcript: the caller's words so far (can be half a sentence).
    Departments are the phone menu's top-level options (e.g. Baggage), plus "Not said yet".
    Returns (department, Jev's confidence 0-1, milliseconds the request took)."""
    response, ms = await ask_jev(transcript, {"department": DEPARTMENT_QUESTION})
    answer = response.choices["department"]
    return answer.choice, answer.confidence, ms


async def classify_partial_transcript(event, guesses, previous):
    """Make one early guess from a partial transcript, then print it as a timeline row.
    event: one Ink-2 event with 't_ms' (ms since the caller started) and 'transcript'.
    guesses: shared list; appends (word time, answer-ready time, pick, confidence).
    previous: the task for the previous word's guess, awaited first so rows print in word order."""
    pick, confidence, ms = await guess_department(event["transcript"])
    
    guesses.append((event["t_ms"], event["t_ms"] + ms, pick, confidence))  # word time, answer-ready time
    
    if previous:
        await previous  # print rows in the order the words arrived
    console.print(f"{event['t_ms']:>6} | {event['type']:<14} | {event['transcript'][-40:]:<40} | {pick} ({confidence:.2f})")


async def listen(turn):
    """Replay one caller's turn, guess on every new word, and report how early Jev was sure.
    turn: one entry from data/turns.json, a name plus its timed Ink-2 events.
    Prints the timeline, then when Jev became confident in the final answer and how much
    silence that saved compared with asking only after the caller finished."""
    console.rule(f"[bold]{turn['name']}")
    

    # 1. Ink-2 streams events. On every new partial transcript, Jev makes a guess in the background.
    guesses, pending = [], []

    async for ev in replay_turn_events(turn):
        kind = ev["type"]
        if kind in ("turn.update", "turn.eager_end"):
            pending.append(asyncio.create_task(classify_partial_transcript(ev, guesses, pending[-1] if pending else None)))
        # 2. The caller kept talking: throw away anything we'd started acting on.
        elif kind == "turn.resume":
            await asyncio.gather(*pending)  # let in-flight guesses print first, so the timeline reads in order
            console.print(f"{ev['t_ms']:>6} | [yellow]{kind:<14} | caller kept talking -> cancel anything started at eager_end[/]")
        elif kind == "turn.start":
            console.print(f"{ev['t_ms']:>6} | {kind}")
    await asyncio.gather(*pending)

    # 3. turn.end: the old way asks Jev only now, on the final transcript.
    t_end, final = ev["t_ms"], ev["transcript"]
    final_pick, _, final_ms = await guess_department(final)
    console.print(f"{t_end:>6} | [bold]turn.end[/]       | {final[-40:]:<40} | [bold]{final_pick}[/]")

    # 4. When did Jev land on the final answer, confidently, and never change its mind after?
    t_knew = None
    for _, t_ready, pick, conf in sorted(guesses):
        if pick == final_pick and conf >= CONFIDENCE_THRESHOLD:
            t_knew = t_knew or t_ready
        else:
            t_knew = None
   
    wait_for_final = t_end + final_ms
    
    if t_knew is None or t_knew >= t_end:
        console.print(f"[red]Jev never got confident early. wait-for-final: {wait_for_final:.0f} ms[/]\n")
        return
    console.print(f"[bold green]JEV KNEW[/] at {t_knew:.0f} ms -> {final_pick}, {t_end - t_knew:.0f} ms before the caller finished")
    console.print(
        f"wait-for-final answers at {wait_for_final:.0f} ms; guessing early already had it"
        f"   ->   [bold green]saved {final_ms:.0f} ms of silence[/]\n"
    )
    # 5. Commit: act on that department, e.g. start the lookup it needs. The LLM and Sonic (TTS) around this don't change.


async def main():
    """Run every scripted caller in data/turns.json, one after another."""
    for turn in TURNS:
        await listen(turn)


asyncio.run(main())
