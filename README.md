# Run three Jev voice-agent demos

Each demo puts [Jev](https://docs.typesafe.ai) between what a caller said and who handles the call. Jev reads the caller's words and returns a decision with a confidence score. Speech-to-text (Cartesia Ink-2), the conversation LLM and text-to-speech (Cartesia Sonic) appear as labels. All demos route calls for Skyline Air, a made-up airline whose phone menu is in `data/airline_ivr.json`.


| File               | What it shows                                                                                |
| ------------------ | -------------------------------------------------------------------------------------------- |
| `ivr_killer.py`    | The caller says one sentence, and Jev picks every phone-menu button for them.                |
| `early_intent.py`  | Jev guesses the destination on every new word and often knows it before the caller finishes. |
| `jev_vs_claude.py` | Jev and Claude Sonnet 5 route the same 150 calls. Compares speed, accuracy and cost.         |


**Result:** At the end, you'll have run all three demos. You'll know it worked when the last one prints a table comparing Claude and Jev.
**Time:** ~15 minutes. The Claude comparison takes about 5 of them.
**Tested on:** macOS 26.6 (Apple Silicon), zsh, 24 Sep 2026

## Before you start

- A Mac with Terminal. To open Terminal, press ⌘ + Space, type `Terminal`, then press Return.



### You'll need

- **A TypeSafe API key.** Create one at [console.typesafe.ai/keys](https://console.typesafe.ai/keys).
- **An Anthropic API key**, used only by `jev_vs_claude.py`. Create one at [platform.claude.com/settings/keys](https://platform.claude.com/settings/keys). Your Anthropic account needs about $1 of credit. One full run costs about $0.40.
- **This folder,** `jev-demos`**, on your Mac.** TODO(maintainer): add the repo URL.



## Steps



### Step 1: Install uv 0.11.19

**Why:** uv installs Python 3.12 and this project's packages for you. If running `uv --version` in Terminal already prints `uv 0.11.19` or newer, skip to Step 2.

**Do this:** In Terminal, paste this and press Return:

```bash
curl -LsSf https://astral.sh/uv/0.11.19/install.sh | sh
```

**You should see:** a line saying `everything's installed!`

**Check it worked:** Close Terminal, open a new Terminal window, then run:

```bash
uv --version
```

Expected: `uv 0.11.19`

**If it didn't work:** `command not found: uv` means Terminal hasn't picked up the new install. Close every Terminal window, open a new one and run the check again.

### Step 2: Go to the project folder

**Why:** Every command after this runs inside `jev-demos`.

**Do this:** In Terminal, type `cd` , with a space after it. Drag the `jev-demos` folder from Finder into the Terminal window, then press Return. Or type the full path instead. For example, if the folder is in Downloads:

```bash
cd ~/path/to/jev-demos
```

**You should see:** your prompt now includes `jev-demos`.

**Check it worked:**

```bash
ls
```

Expected: the list includes `ivr_killer.py`, `early_intent.py` and `jev_vs_claude.py`.

**If it didn't work:** `No such file or directory` means the path is wrong. Drag the folder in again.

### Step 3: Install the project

**Why:** This downloads Python 3.12 and the four packages the demos use.

**Do this:** In Terminal, run:

```bash
uv sync
```

**You should see:** a line starting with `Resolved 24 packages`, after 10–60 seconds.

**Check it worked:**

```bash
uv run python3 --version
```

Expected: a line starting with `Python 3.12`

**If it didn't work:** `No pyproject.toml found` means you're in the wrong folder. Go back to Step 2.

### Step 4: Add your API keys

**Why:** The demos read both keys from a file named `.env`.

**Do this:** In Terminal, run:

```bash
cp -n .env.example .env
```

TextEdit opens with two lines, each ending in `=`. Paste each key straight after its `=` sign, with no spaces or quotes. When you're done, the file looks like this, with your real keys:

```text
TYPESAFE_API_KEY=paste-your-typesafe-key-here
ANTHROPIC_API_KEY=paste-your-anthropic-key-here
```

Save with ⌘ + S, then close TextEdit.

**You should see:** the Terminal prompt again, with no output.

**Check it worked:**

```bash
grep -c '=.' .env
```

Expected: `2`

**If it didn't work:** `1` or `0` means a key is missing. Run `open -e .env` and paste the missing key.

### Step 5: Run the phone-menu demo

**Why:** Five example callers, one sentence each.

**Do this:** In Terminal, run:

```bash
uv run ivr_killer.py
```

**You should see:** five calls. Each one shows the menu Jev picked with a confidence score, a menu tree with the chosen path in green, and a comparison like this:

```text
touch-tone: 2 menus heard, ~30s of listening   vs   Jev: 1 sentence, total 963 ms
```

The last caller is angry, so Jev skips the menus and prints `-> escalating straight to a human`.

**Check it worked:** try a sentence of your own:

```bash
uv run ivr_killer.py "my suitcase came off the carousel with the wheels smashed"
```

Expected: `Transfer to: Baggage claims team`

**If it didn't work:** `TypeSafeAuthenticationError` means the TypeSafe key is wrong. Fix it in `.env` (Step 4).

### Step 6: Run the early-intent demo

**Why:** Four callers replayed word by word, with real pauses.

**Do this:** In Terminal, run:

```bash
uv run early_intent.py
```

**You should see:** after about 30 seconds, one timeline per caller that ends like this:

```text
JEV KNEW at 2396 ms -> Baggage
wait-for-final: 6755 ms   vs   speculative: 2396 ms   ->   saved 4358 ms
```

**Check it worked:** each of the four timelines ends with either a `saved ... ms` line or `Jev never got confident early`. Both are normal. The second means Jev wasn't confident enough before the caller finished.

**If it didn't work:** `TypeSafeAuthenticationError` means the TypeSafe key is wrong. Fix it in `.env` (Step 4).

Each demo acts only when Jev's confidence is at or above `CONFIDENCE = 0.95`, near the top of the file. To try a lower threshold, run `open -e early_intent.py`, change `0.95` to a number such as `0.9`, save with ⌘ + S and run the demo again.

### Step 7: Run the Claude comparison

**Why:** The same 150 calls, sent to Claude and to Jev.

**Do this:** In Terminal, run:

```bash
uv run jev_vs_claude.py
```

**You should see:** one progress line per call (`1/150` to `150/150`) over about 5 minutes, then a table titled `Routing: Claude Sonnet 5 vs Jev`, two grids of right and wrong answers, and a cost line.

**Check it worked:** the table's first row shows two speeds, like this:

```text
latency p50 / p95 (ms)  │ 1620 / 2900 │ 372 / 542
```

The first column is Claude and the second is Jev. p50 is the typical call and p95 is the slowest 5%. To print the table again without calling the APIs, run `uv run jev_vs_claude.py --report`.

**If it didn't work:** `AuthenticationError` means the Anthropic key is wrong. Fix it in `.env` (Step 4). A billing or credit error means your Anthropic account needs credit.

## Undo / clean up

1. In Finder, drag the `jev-demos` folder to the Trash. This also deletes `.env` and the API keys in it.
2. If you installed uv in Step 1 and want it gone, run these in Terminal, one at a time:

```bash
uv cache clean
```

```bash
rm -rf "$(uv python dir)"
```

```bash
rm ~/.local/bin/uv ~/.local/bin/uvx
```

