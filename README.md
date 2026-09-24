# Run three Jev voice-agent demos

Each demo puts [Jev](https://docs.typesafe.ai) between what a caller said and who handles the call. Jev reads the caller's words and returns a decision with a confidence score. Speech-to-text (Cartesia Ink-2), the conversation LLM and text-to-speech (Cartesia Sonic) appear as labels. All demos route calls for Skyline Air, a made-up airline whose phone menu is in `data/airline_ivr.json`.


| File               | What it shows                                                                                |
| ------------------ | -------------------------------------------------------------------------------------------- |
| `ivr_killer.py`    | The old way: menus and buttons. The new way: one sentence, and Jev picks the team.           |
| `early_intent.py`  | Jev guesses the destination on every new word and often knows it before the caller finishes. |
| `jev_vs_claude.py` | Jev and Claude Sonnet 5 route the same calls (up to 150). Compares speed, accuracy and cost. |


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

**Why:** This downloads Python 3.12 and the four packages the demos use into a `.venv` folder in the project.

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

## Demo 1: Kill the IVR (`ivr_killer.py`)

Five example callers. For each one you see the old way, an IVR system's menu tree with the buttons a person would press, then the new way, where Jev picks the team from the caller's one sentence.

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

### Try your own sentence

```bash
uv run ivr_killer.py "my suitcase came off the carousel with the wheels smashed"
```

Expected: `Transfer to: Baggage claims team`

**If it didn't work:** `TypeSafeAuthenticationError` means the TypeSafe key is wrong. Fix it in `.env` (Step 4).

## Demo 2: It knew before you finished (`early_intent.py`)

Four callers replayed word by word, with real pauses. Jev guesses on every new word.

### Run it

```bash
uv run early_intent.py
```

**You should see:** after about 30 seconds, one timeline per caller that ends like this:

```text
JEV KNEW at 2396 ms -> Baggage
wait-for-final: 6755 ms   vs   speculative: 2396 ms   ->   saved 4358 ms
```

Each timeline ends with either a `saved ... ms` line or `Jev never got confident early`. Both are normal. The second means Jev wasn't confident enough before the caller finished.

**If it didn't work:** `TypeSafeAuthenticationError` means the TypeSafe key is wrong. Fix it in `.env` (Step 4).

### Change the confidence threshold

Each demo acts only when Jev's confidence is at or above `CONFIDENCE_THRESHOLD = 0.95`, near the top of the file. Change it to a number such as `0.9`, save, and run the demo again.

## Demo 3: Replace your routing LLM with Jev (`jev_vs_claude.py`)

The same calls, sent to Claude and to Jev, then both are scored.

### Run it

Start with 10 calls, which takes under a minute:

```bash
uv run jev_vs_claude.py 10
```

For all 150 calls, which takes about 5 minutes, leave off the number:

```bash
uv run jev_vs_claude.py
```

**You should see:** one progress line per call with both speeds, like `3/10 claude 1003 ms  jev 282 ms | ...`. Then a table titled `Routing: Claude Sonnet 5 vs Jev`, two grids of right and wrong answers, and a cost line. The table's first row shows two speeds:

```text
latency p50 / p95 (ms)  │ 1620 / 2900 │ 372 / 542
```

The first column is Claude and the second is Jev. p50 is the typical call and p95 is the slowest 5%. To print the last table again without calling the APIs, run `uv run jev_vs_claude.py --report`.

**If it didn't work:** `AuthenticationError` means the Anthropic key is wrong. Fix it in `.env` (Step 4). A billing or credit error means your Anthropic account needs credit.

## Undo / clean up

1. Delete the project folder. This also deletes `.env` and the API keys in it.
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
