"""
MENTAL MODEL: In a multi-agent voice system, a router decides: stay, or hand off to agent X.
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

from lib.jev import IVR, ask

CONFIDENCE_THRESHOLD = 0.95
RESULTS = "results/rows.json"
ALL_ROWS = [json.loads(line) for line in open("data/transcripts.jsonl")]
RUNS = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].isdigit() else len(ALL_ROWS)
ROWS = random.Random(0).sample(ALL_ROWS, min(RUNS, len(ALL_ROWS)))  # fixed seed: same mix of categories every run
console = Console()

# 1. The agents. Same one-line descriptions for both routers.
AGENTS = {option["label"]: option["description"] for option in IVR["options"]}
AGENTS["stay"] = "No handoff: greetings, thanks, small talk, or general travel questions the current agent can answer (check-in, security, airport, onboard services)"

# 2. Router A: Claude, with one transfer tool per agent. No tool call = stay.
claude = AsyncAnthropic()
TOOL_TO_AGENT = {f"transfer_to_{label.split()[0].lower()}": label for label in AGENTS if label != "stay"}
TOOLS = [{"name": name, "description": AGENTS[label], "input_schema": {"type": "object", "properties": {}}} for name, label in TOOL_TO_AGENT.items()]
SYSTEM = "You route calls for Skyline Air's phone line. If the caller needs another department, call that transfer tool. Otherwise don't call any tool."


async def route_with_claude(text):
    start, pick, ms = time.perf_counter(), "stay", None
    async with claude.messages.stream(
        model="claude-sonnet-5", max_tokens=200, thinking={"type": "disabled"}, system=SYSTEM, tools=TOOLS, messages=[{"role": "user", "content": text}]
    ) as stream:
        async for event in stream:
            if event.type == "content_block_start" and event.content_block.type == "tool_use" and ms is None:
                pick, ms = TOOL_TO_AGENT[event.content_block.name], (time.perf_counter() - start) * 1000  # tool name appeared
        usage = (await stream.get_final_message()).usage
    ms = ms or (time.perf_counter() - start) * 1000  # no tool: we only know it's "stay" at end of stream
    return {"pick": pick, "ms": ms, "usd": (usage.input_tokens * 2 + usage.output_tokens * 10) / 1e6}


# 3. Router B: Jev, one Choice over the same agents.
ROUTER = Choice(instructions="Skyline Air phone line router. Which agent should handle what the caller just said?", criteria=AGENTS)


async def route_with_jev(text):
    response, ms = await ask(text, {"agent": ROUTER})
    answer = response.choices["agent"]
    return {"pick": answer.choice, "ms": ms, "conf": answer.confidence, "usd": response.usage.input_tokens * 0.042 / 1e6}


async def run_bench():
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
def percentile(values, p):
    return sorted(values)[int(p * (len(values) - 1))]


def precision_recall(rows, arm, label, to_class=lambda x: x):
    picked = [r for r in rows if to_class(r[arm]["pick"]) == label]
    actual = [r for r in rows if to_class(r["expected"]) == label]
    hits = [r for r in picked if to_class(r["expected"]) == label]
    return len(hits) / max(len(picked), 1), len(hits) / max(len(actual), 1)


def print_report(rows):
    arms = ["claude", "jev"]
    table = Table(title="Routing: Claude Sonnet 5 vs Jev")
    table.add_column("metric")
    for arm in arms:
        table.add_column(arm, justify="right")
    table.add_row("latency p50 / p95 (ms)", *[f"{percentile([r[a]['ms'] for r in rows], .5):.0f} / {percentile([r[a]['ms'] for r in rows], .95):.0f}" for a in arms])
    table.add_row("accuracy", *[f"{sum(r[a]['pick'] == r['expected'] for r in rows) / len(rows):.0%}" for a in arms])
    handoff = lambda label: "stay" if label == "stay" else "handoff"
    for label in ["handoff", "stay"] + [a for a in AGENTS if a != "stay"]:
        name = "  " + label if label in AGENTS and label != "stay" else f"[bold]{label}[/]"
        to_class = handoff if label in ("handoff", "stay") else (lambda x: x)
        table.add_row(f"{name} P / R", *["%.2f / %.2f" % precision_recall(rows, a, label, to_class) for a in arms])
    for category in dict.fromkeys(r["category"] for r in rows):
        subset = [r for r in rows if r["category"] == category]
        table.add_row(f"acc: {category}", *[f"{sum(r[a]['pick'] == r['expected'] for r in subset) / len(subset):.0%}" for a in arms])
    confident = [r for r in rows if r["jev"]["conf"] >= CONFIDENCE_THRESHOLD]
    table.add_row(f"jev conf >= {CONFIDENCE_THRESHOLD}", "", f"{len(confident)} rows, {sum(r['jev']['pick'] == r['expected'] for r in confident) / max(len(confident), 1):.0%} right")
    console.print(table)

    short = {label: label.split()[0][:8] for label in AGENTS}
    for arm in arms:
        matrix = Table(title=f"{arm}: expected (rows) vs picked (columns)")
        matrix.add_column("")
        for label in AGENTS:
            matrix.add_column(short[label], justify="right")
        for expected in AGENTS:
            counts = [sum(r["expected"] == expected and r[arm]["pick"] == picked for r in rows) for picked in AGENTS]
            matrix.add_row(short[expected], *[f"[green]{n}[/]" if e == expected else str(n or "") for n, e in zip(counts, AGENTS)])
        console.print(matrix)

    cost = {a: sum(r[a]["usd"] for r in rows) / len(rows) * 1000 for a in arms}
    console.print(f"[dim]$ per 1k routing calls: claude ${cost['claude']:.2f}  jev ${cost['jev']:.4f}  (Sonnet 5 $2/$10 per Mtok in/out; Jev $0.042 per Mtok in)[/]")


if "--report" not in sys.argv:
    asyncio.run(run_bench())
print_report(json.load(open(RESULTS)))
