# Run three Jev voice-agent demos

These demos show when a voice agent should use a decision model like [Jev](https://docs.typesafe.ai) instead of an LLM, compared on speed, cost and accuracy. Jev reads the caller's words and returns an answer with probabilities and a confidence score. You pay only for input tokens ($0.042 per million); output is free. Speech-to-text (Cartesia Ink-2), the conversation LLM and text-to-speech (Cartesia Sonic) appear as labels. All demos use HiFly Airlines, a made-up airline whose phone menu is in `data/airline_ivr.json`.


| File               | What it shows                                                                                                   |
| ------------------ | --------------------------------------------------------------------------------------------------------------- |
| `early_intent.py`  | Act early: detect what the caller wants while they're still talking. Only fast, cheap per-update decisions allow this. |
| `ivr_killer.py`    | Cut hold time: one sentence replaces ~30 s of phone menus, and Jev's confidence decides transfer, follow-up or escalate. |
| `jev_vs_claude.py` | The same decision, Claude Sonnet 5 vs Jev, on 150 calls: speed, accuracy and cost side by side.                  |


**Result:** At the end, you'll have run all three demos. You'll know it worked when the last one prints a table comparing Claude and Jev.
**Time:** ~15 minutes. The full Claude comparison takes about 5 of them.
**Tested on:** macOS 26.6 (Apple Silicon), zsh, 24 Sep 2026

## Before you start

- A Mac with a code editor such as Cursor or VS Code, with its Python extension installed. Run every command in the editor's built-in terminal.
- git. If macOS asks to install the command line developer tools when you first run `git`, click **Install**, then run the command again.

### You'll need

- **A TypeSafe API key.** Create one at [console.typesafe.ai/keys](https://console.typesafe.ai/keys).
- **An Anthropic API key**, used only by `jev_vs_claude.py`. Create one at [platform.claude.com/settings/keys](https://platform.claude.com/settings/keys). Your Anthropic account needs about $1 of credit. One full run costs about $0.40.
- **The repo URL** for this project.

## Set up

### Step 1: Install uv 0.11.19

**Why:** uv installs Python 3.12 and this project's packages for you. If `uv --version` already prints `uv 0.11.19` or newer, skip to Step 2.

**Do this:**

```bash
curl -LsSf https://astral.sh/uv/0.11.19/install.sh | sh
```

**You should see:** a line saying `everything's installed!`

**Check it worked:** close the terminal, open a new one, then run:

```bash
uv --version
```

Expected: `uv 0.11.19`

**If it didn't work:** `command not found: uv` means the terminal hasn't picked up the new install. Restart your editor and run the check again.

### Step 2: Clone the repo

**Do this:** replace `<repo-url>` with the repo URL, then run:

```bash
git clone <repo-url>
```

git creates a folder named after the repo. Go into it, then open that folder in your editor:

```bash
cd jev-demos
```

**You should see:** your prompt now includes the folder name.

**If it didn't work:** `No such file or directory` means the folder has a different name. Run `ls` and `cd` into the folder git created.

### Step 3: Install the project

**Why:** This downloads Python 3.12 and the packages the demos use into a `.venv` folder in the project.

**Do this:**

```bash
uv sync
```

**You should see:** a line starting with `Resolved 24 packages`, after 10–60 seconds.

**Check it worked:**

```bash
uv run python3 --version
```

Expected: a line starting with `Python 3.12`

You don't need to activate the virtual environment: `uv run` uses `.venv` for you. To stop your editor underlining imports in red, point it at the same Python: press ⌘ + Shift + P, choose **Python: Select Interpreter**, then pick the one in `.venv`.

**If it didn't work:** `No pyproject.toml found` means you're in the wrong folder. Go back to Step 2.

### Step 4: Add your API keys

**Why:** The demos read both keys from a file named `.env`. git ignores `.env`, so your keys are never committed.

**Do this:**

```bash
cp -n .env.example .env
```

Open `.env` in your editor. It has two lines, each ending in `=`. Paste each key straight after its `=` sign, with no spaces or quotes, then save. When you're done, it looks like this, with your real keys:

```text
TYPESAFE_API_KEY=paste-your-typesafe-key-here
ANTHROPIC_API_KEY=paste-your-anthropic-key-here
```

**Check it worked:**

```bash
grep -c '=.' .env
```

Expected: `2`

**If it didn't work:** `1` or `0` means a key is missing. Open `.env` and paste the missing key.

## Demo 1: It knew before you finished (`early_intent.py`)

Four callers replayed word by word, with real pauses. Jev guesses on every new word.

**What it shows:** a voice agent can detect what the caller wants while they're still talking, and start an action early, such as looking up their booking. That needs a decision on every transcript update. Jev takes about 280 ms per decision and charges only for input. In Demo 3, Claude Sonnet 5 took about 1.6 s per decision, slower than new words arrive, and cost about 120 times more.

### Run it

```bash
uv run early_intent.py
```

**You should see:** after about 30 seconds, one timeline per caller that ends like this:

```text
JEV KNEW at 2396 ms -> Baggage, 4004 ms before the caller finished
wait-for-final answers at 6755 ms; guessing early already had it   ->   saved 355 ms of silence
```

Each timeline ends with either a `saved ... ms` line or `Jev never got confident early`. Both are normal. The second means Jev wasn't confident enough before the caller finished.

**If it didn't work:** `TypeSafeAuthenticationError` means the TypeSafe key is wrong. Fix it in `.env` (Step 4).

### Change the confidence threshold

Open `early_intent.py`. Jev counts as confident only when its confidence is at or above `CONFIDENCE_THRESHOLD = 0.95`, near the top of the file. Change it to a number such as `0.9`, save, and run the demo again.

## Demo 2: Kill the IVR (`ivr_killer.py`)

Five example callers. For each one you see the old way, an IVR system's menu tree with the buttons a person would press, then the new way, where Jev picks the team from the caller's one sentence.

**What it shows:** one sentence replaces about 30 seconds of menus. Jev picks the team and flags callers who need a human in one request, and its confidence decides whether to transfer, ask one follow-up question or escalate. An LLM could pick the team too, but in Demo 3 it was about 6 times slower and 120 times more expensive per decision.

### Run it

```bash
uv run ivr_killer.py
```

**You should see:** five calls. Each one shows the full IVR tree with the pressed path in green, how long the caller would listen, then Jev's answer:

```text
IVR system: 2 menus heard, ~30s of listening
...
Jev chose: Baggage claims team | confidence: 0.97 | latency 835 ms
Transfer to: Baggage claims team
```

The second caller is vague, so Jev isn't confident and the agent asks one follow-up question. The last caller is angry, so Jev prints `-> escalating straight to a human`.

To run only some examples, pass their indexes (0 to 4), e.g. `uv run ivr_killer.py 1`.

**If it didn't work:** `TypeSafeAuthenticationError` means the TypeSafe key is wrong. Fix it in `.env` (Step 4).

## Demo 3: Jev vs Claude, the same decision (`jev_vs_claude.py`)

The same calls, sent to Claude and to Jev, then both are scored.

**What it shows:** in our 150-call run, Jev was more accurate (92% vs 85%), about 6 times faster (277 ms vs 1612 ms typical) and about 120 times cheaper ($0.021 vs $2.58 per 1,000 calls). When Jev's confidence was 0.95 or higher, it was right 98% of the time. Your numbers will vary a little.

### Run it

Start with 10 calls, which takes under a minute:

```bash
uv run jev_vs_claude.py 10
```

For all 150 calls, which takes about 5 minutes, leave off the number:

```bash
uv run jev_vs_claude.py
```

**You should see:** one progress line per call with both speeds, like `3/10 claude 1003 ms  jev 282 ms | ...`. Then a table titled `Routing: Claude Sonnet 5 vs Jev (150 calls)` (or `10 calls`), two grids of right and wrong answers, and a cost line. The table's first row shows two speeds:

```text
latency p50 / p95 (ms)  │ 1612 / 3315 │ 277 / 407
```

The first column is Claude and the second is Jev. p50 is the typical call and p95 is the slowest 5%. To print the last table again without calling the APIs, run `uv run jev_vs_claude.py --report`.

**If it didn't work:** `AuthenticationError` means the Anthropic key is wrong. Fix it in `.env` (Step 4). A billing or credit error means your Anthropic account needs credit.

## Undo / clean up

1. Delete the project folder. This also deletes `.env` and the API keys in it. From inside the folder, run:

```bash
cd .. && rm -rf jev-demos
```

2. If you installed uv in Step 1 and want it gone, run these one at a time:

```bash
uv cache clean
```

```bash
rm -rf "$(uv python dir)"
```

```bash
rm ~/.local/bin/uv ~/.local/bin/uvx
```
