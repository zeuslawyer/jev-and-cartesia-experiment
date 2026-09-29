"""
MENTAL MODEL: In a multi-agent voice system, a router decides: no handoff (the current agent keeps the call), or hand off to agent X.
Today that's usually an LLM tool call. Jev replaces that router and runs before the
conversation LLM. Same transcripts, same agent descriptions, two routers. Who's faster and more accurate?
Run once to call the APIs; add --report to re-print from saved results without calling anything.
Pass a number to route fewer calls, e.g. `uv run jev_vs_claude.py 10`.
"""
import asyncio
import json
import os
import random
import sys
import time

from anthropic import AsyncAnthropic
from rich.console import Console
from rich.table import Table
from typesafe_sdk import Choice

from lib.jev import IVR, ask_jev

CONFIDENCE_THRESHOLD = 0.95
RESULTS = "results/rows.json"
ALL_ROWS = [json.loads(line) for line in open("data/transcripts.jsonl")]
RUNS = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].isdigit() else len(ALL_ROWS)
ROWS = random.Random(0).sample(ALL_ROWS, min(RUNS, len(ALL_ROWS)))  # fixed seed: same mix of categories every run
console = Console()

# 1. The agents. Same one-line descriptions for both routers.
AGENTS = {option["label"]: option["description"] for option in IVR["options"]}
# "no handoff" = the agent already on the call keeps it.
AGENTS["no handoff"] = "No handoff: greetings, thanks, small talk, or general travel questions the current agent can answer (check-in, security, airport, onboard services)"

# 2. Router A: Claude, with one transfer tool per agent. No tool call = no handoff.
claude = AsyncAnthropic()
TOOL_TO_AGENT = {f"transfer_to_{label.split()[0].lower()}": label for label in AGENTS if label != "no handoff"}
TOOLS = [{"name": name, "description": AGENTS[label], "input_schema": {"type": "object", "properties": {}}} for name, label in TOOL_TO_AGENT.items()]
SYSTEM = f"You route calls for HiFly Airlines's phone line. If the caller needs another department, call that transfer tool. Otherwise don't call any tool. {AGENTS['no handoff']}."


async def route_with_claude(text):
    """Ask Claude which agent should handle what the caller said.
    text: one caller line. Claude gets one transfer tool per agent; no tool call means "no handoff".
    Returns {'pick': agent label, 'ms': time until the tool name appeared (or the stream ended), 'usd': cost}."""
    start, pick, ms = time.perf_counter(), "no handoff", None
    async with claude.messages.stream(
        model="claude-sonnet-5", max_tokens=200, thinking={"type": "disabled"}, system=SYSTEM, tools=TOOLS, messages=[{"role": "user", "content": text}]
    ) as stream:
        async for event in stream:
            if event.type == "content_block_start" and event.content_block.type == "tool_use" and ms is None:
                pick, ms = TOOL_TO_AGENT[event.content_block.name], (time.perf_counter() - start) * 1000  # tool name appeared
        usage = (await stream.get_final_message()).usage
    ms = ms or (time.perf_counter() - start) * 1000  # no tool: we only know it's "no handoff" at end of stream
    return {"pick": pick, "ms": ms, "usd": (usage.input_tokens * 2 + usage.output_tokens * 10) / 1e6}


# 3. Router B: Jev, one Choice over the same agents.
ROUTER = Choice(instructions="HiFly Airlines phone line router. Which agent should handle what the caller just said?", criteria=AGENTS)


async def route_with_jev(text):
    """Ask Jev the same question: which agent should handle what the caller said?
    text: one caller line.
    Returns {'pick': agent label, 'ms': request time, 'conf': Jev's confidence 0-1, 'usd': cost (input tokens only)}."""
    response, ms = await ask_jev(text, {"agent": ROUTER})
    answer = response.choices["agent"]
    return {"pick": answer.choice, "ms": ms, "conf": answer.confidence, "usd": response.usage.input_tokens * 0.042 / 1e6}


async def run_bench():
    """Send every sampled caller line to Claude, then Jev, printing one progress line per call.
    Side effect: writes all results to results/rows.json, which --report reads back."""
    for i, row in enumerate(ROWS, 1):
        row["claude"] = await route_with_claude(row["text"])
        row["jev"] = await route_with_jev(row["text"])
        console.print(
            f"[dim]{i}/{len(ROWS)}[/] claude {row['claude']['ms']:>5.0f} ms  jev {row['jev']['ms']:>4.0f} ms | "
            f"claude={row['claude']['pick']}  jev={row['jev']['pick']}  expected={row['expected']}"
        )
    os.makedirs("results", exist_ok=True)
    json.dump(ROWS, open(RESULTS, "w"), indent=1)


# 4. Score both routers. Plain counting, no libraries.
def pick_percentile(values, p):
    """Return the value at fraction p of the sorted list, e.g. p=0.5 is the typical (median) value."""
    return sorted(values)[int(p * (len(values) - 1))]


def score_precision_recall(rows, arm, label, to_class=lambda x: x):
    """Score one model on one label.
    rows: scored calls. arm: 'claude' or 'jev'. label: an agent name, or 'handoff' / 'no handoff'.
    to_class: maps an agent name to the label being scored (e.g. any agent -> 'handoff').
    Returns text like "1.00 (12/12) / 0.60 (12/20)".
    Precision: of the calls it sent to label, the share that belonged there (hits / sent).
    Recall: of the calls that belonged to label, the share it sent there (hits / belonged)."""
    sent = sum(to_class(r[arm]["pick"]) == label for r in rows)
    belonged = sum(to_class(r["expected"]) == label for r in rows)
    hits = sum(to_class(r[arm]["pick"]) == label and to_class(r["expected"]) == label for r in rows)
    return f"{hits / max(sent, 1):.2f} ({hits}/{sent}) / {hits / max(belonged, 1):.2f} ({hits}/{belonged})"


def print_report(rows):
    """Print the comparison: latency, accuracy, precision/recall, accuracy per kind of caller,
    Jev's high-confidence hit rate, and cost per 1,000 calls.
    rows: scored calls, as saved in results/rows.json."""
    arms = ["claude", "jev"]
    table = Table(title=f"Routing: Claude Sonnet 5 vs Jev ({len(rows)} calls)", caption="precision = right / sent there    recall = right / belonged there")
    table.add_column("metric")
    for arm in arms:
        table.add_column(arm, justify="right")
    table.add_row("latency p50 typical / p95 slow end (ms)", *[f"{pick_percentile([r[a]['ms'] for r in rows], .5):.0f} / {pick_percentile([r[a]['ms'] for r in rows], .95):.0f}" for a in arms])
    table.add_row("accuracy (all calls)", *[f"{sum(r[a]['pick'] == r['expected'] for r in rows) / len(rows):.0%}" for a in arms])
    handoff = lambda label: "no handoff" if label == "no handoff" else "handoff"
    summary_names = {"handoff": "handoff (to any agent)", "no handoff": "no handoff (current agent keeps the call)"}
    table.add_row("[bold]precision / recall[/]", "", "")
    for label in ["no handoff", "handoff"] + [a for a in AGENTS if a != "no handoff"]:
        name = "  " + label if label in AGENTS and label != "no handoff" else f"[bold]{summary_names[label]}[/]"
        to_class = handoff if label in ("handoff", "no handoff") else (lambda x: x)
        table.add_row(name, *[score_precision_recall(rows, a, label, to_class) for a in arms])
    category_names = {"no_handoff": "no handoff", "multi_intent": "two requests in one"}
    for category in dict.fromkeys(r["category"] for r in rows):
        subset = [r for r in rows if r["category"] == category]
        table.add_row(f"accuracy: {category_names.get(category, category)}", *[f"{sum(r[a]['pick'] == r['expected'] for r in subset) / len(subset):.0%}" for a in arms])
    confident = [r for r in rows if r["jev"]["conf"] >= CONFIDENCE_THRESHOLD]
    table.add_row(f"jev confidence ≥ {CONFIDENCE_THRESHOLD}", "", f"{len(confident)} calls, {sum(r['jev']['pick'] == r['expected'] for r in confident) / max(len(confident), 1):.0%} right")
    console.print(table)

    cost = {a: sum(r[a]["usd"] for r in rows) / len(rows) * 1000 for a in arms}
    console.print(f"[dim]$ per 1k routing calls: claude ${cost['claude']:.2f}  jev ${cost['jev']:.4f}  (Sonnet 5 $2/$10 per Mtok in/out; Jev $0.042 per Mtok in)[/]")


if "--report" not in sys.argv:
    asyncio.run(run_bench())
print_report(json.load(open(RESULTS)))
