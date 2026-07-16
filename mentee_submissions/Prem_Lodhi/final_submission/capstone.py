"""
capstone.py — Planner Agent
VECTOR: A disciplined AI project manager.

Architecture:
  State Layer   : load_plan, save_plan, get_step         → plan.json
  Shield        : call_llm                               → 429 backoff
  Planner       : make_plan                              → goal decomposition
  Context       : build_step_context                     → bounded TPM
  Executor      : execute_step                           → inner ReAct loop
  Outer Loop    : run                                    → state machine driver

Organs:
  Voice  → PLANNER_PERSONA (system prompt)
  Hands  → search_the_web, open_page (tools)
  Brain  → inner ReAct while-loop inside execute_step
  Self   → plan.json surviving Ctrl-C and restart
"""

import os
import re
import json
import time
from dotenv import load_dotenv
from groq import Groq, RateLimitError
from playwright.sync_api import sync_playwright

# ─────────────────────────────────────────────────────────────────
# 1. Setup
# ─────────────────────────────────────────────────────────────────
load_dotenv()
MODEL     = "meta-llama/llama-4-scout-17b-16e-instruct"  # swap if needed
PLAN_FILE = "plan.json"

# Lazy client: created once on first call_llm() call, not on import.
# This means the file imports cleanly even without GROQ_API_KEY in env —
# the key is only needed when you actually make an API call (Phase 2+).
_client = None

def get_client() -> Groq:
    """Return the singleton Groq client, initializing it on first call."""
    global _client
    if _client is None:
        _client = Groq()   # reads GROQ_API_KEY from env at this point
    return _client


# ─────────────────────────────────────────────────────────────────
# 2. STATE LAYER   (Phase 1)
#    No API calls here — pure disk I/O.
#    Everything else in the file depends on these three functions.
# ─────────────────────────────────────────────────────────────────

def load_plan() -> dict:
    """
    Read plan.json from disk.

    Returns {} in two safe-failure cases:
      • file doesn't exist yet   → first run, no plan written yet
      • file is corrupt JSON     → crash happened mid-write last run

    The caller (run()) treats {} as "no plan → call make_plan()".
    """
    if not os.path.exists(PLAN_FILE):
        return {}
    with open(PLAN_FILE, "r") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            # Half-written file from a crash. Start fresh rather than explode.
            print(f"[WARN] {PLAN_FILE} was corrupt. Starting fresh.")
            return {}


def save_plan(plan: dict) -> None:
    """
    Write the plan dict to plan.json.

    Two-step write (write to .tmp, then rename) so that a crash
    mid-write never leaves a corrupt plan.json — the rename is
    atomic on all POSIX systems (Linux/macOS).
    """
    tmp_path = PLAN_FILE + ".tmp"
    with open(tmp_path, "w") as f:
        json.dump(plan, f, indent=2)
    os.replace(tmp_path, PLAN_FILE)   # atomic on POSIX — safe to Ctrl-C


def get_step(plan: dict, step_id: int):
    """
    Return the step dict whose 'id' matches step_id, or None.

    Used in two places:
      • build_step_context: to look up the previous step's result
      • run:               to find the first non-done step
    """
    for step in plan.get("steps", []):
        if step["id"] == step_id:
            return step
    return None


# ─────────────────────────────────────────────────────────────────
# 3. SHIELD — call_llm with 429 backoff   (Phase 2)
# ─────────────────────────────────────────────────────────────────

def call_llm(messages, tools=None, max_retries=5):
    """
    Single entry-point for every Groq API call in this project.

    Retry strategy — exponential backoff on HTTP 429 (RateLimitError):
      attempt 1 failed → sleep 2s
      attempt 2 failed → sleep 4s
      attempt 3 failed → sleep 8s  ...doubles each time
      attempt N == max_retries → re-raise, do not swallow

    Stretch: if the 429 response carries a Retry-After header,
    sleep for exactly that duration instead of the backoff delay.
    The backoff counter still doubles so subsequent non-header errors
    get the correct next interval.

    tool_choice:
      tools=None  → omit tool_choice entirely (don't force tool use)
      tools=[...] → tool_choice="auto"  (model picks if/when to call)
    """
    delay = 2  # seconds; doubles on each rate-limited attempt
    for attempt in range(max_retries):
        try:
            # Build arguments dynamically to avoid sending 'None' values to the API
            kwargs = {
                "model": MODEL,
                "messages": messages,
            }
            if tools:
                kwargs["tools"] = tools
                kwargs["tool_choice"] = "auto"
                
            return get_client().chat.completions.create(**kwargs)
        except RateLimitError as e:
            if attempt == max_retries - 1:
                raise  # out of retries — let it propagate

            # ── Stretch: honour Retry-After header when present ──
            sleep_time = None
            if hasattr(e, "response") and e.response is not None:
                header_val = e.response.headers.get("Retry-After")
                if header_val is not None:
                    try:
                        sleep_time = float(header_val)
                    except (ValueError, TypeError):
                        pass  # malformed header — fall back to backoff

            if sleep_time is None:
                sleep_time = delay

            print(f"  [rate-limited] attempt {attempt + 1}/{max_retries}"
                  f" — sleeping {sleep_time}s…")
            time.sleep(sleep_time)
            delay *= 2  # advance backoff regardless of which sleep path was used


# ─────────────────────────────────────────────────────────────────
# 4. TOOLS — Hands organ   (Phase 4)
# ─────────────────────────────────────────────────────────────────

def search_the_web(query: str) -> str:
    """
    Search the web via DuckDuckGo and return the top 5 results as
    a readable text block.

    No API key needed — DDGS scrapes DDG's HTML endpoint.
    Returns a "No results found." sentinel if DDG returns nothing
    so the model can react gracefully instead of seeing an exception.
    """
    from duckduckgo_search import DDGS
    hits = []
    with DDGS() as ddgs:
        for r in ddgs.text(query, max_results=5):
            hits.append(f"• {r['title']}\n  {r['href']}\n  {r['body']}")
    return "\n\n".join(hits) if hits else "No results found."


def open_page(url: str) -> str:
    """
    Fetch a URL with a headless Chromium browser and return its visible
    body text, capped at 3 000 characters.

    The hard cap exists because this text goes straight into the context
    window — an uncapped page can easily blow past the model's TPM limit.
    Playwright is used (over requests) so JS-rendered pages work too.
    """
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(url, timeout=15_000)
        text = page.inner_text("body")
        browser.close()
    return text[:3_000]


# Tool schemas — Groq uses the OpenAI function-calling format.
# Name in "name" must exactly match the Python function name so
# available_tools[fn_name](**fn_args) resolves correctly in execute_step.
tools = [
    {
        "type": "function",
        "function": {
            "name": "search_the_web",
            "description": (
                "Search the web for up-to-date information on a topic or question. "
                "Use this before open_page to find relevant URLs."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query to look up.",
                    }
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "open_page",
            "description": (
                "Fetch and return the readable text content of a web page. "
                "Use a URL returned by search_the_web."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "The full URL (including https://) to fetch.",
                    }
                },
                "required": ["url"],
            },
        },
    },
]

# Dispatch dict: fn_name (string from tool_call) → callable.
# execute_step does: available_tools[fn_name](**fn_args)
available_tools = {
    "search_the_web": search_the_web,
    "open_page":      open_page,
}


# ─────────────────────────────────────────────────────────────────
# 5. VOICE — Planner persona   (Phase 4)
# ─────────────────────────────────────────────────────────────────

PLANNER_PERSONA = (
    "You are VECTOR, a disciplined AI project manager. "
    "You execute one assigned task at a time with precision. "
    "If a tool is needed to complete the task, use it. "
    "When done, report the result clearly and concisely. "
    "Never do more than the task asks. Never do less."
)


# ─────────────────────────────────────────────────────────────────
# 6. PLANNER — make_plan   (Phase 3)
# ─────────────────────────────────────────────────────────────────

DECOMPOSER_PROMPT = (
    "You are a project decomposition engine. "
    "Break the goal into 4-7 clear, sequential, self-contained steps. "
    "Respond with ONLY a raw JSON array. No markdown. No preamble. No explanation. "
    'Each element: {"id": N, "task": "one complete instruction"}'
)


def extract_json(text: str):
    """
    Strip ```json ... ``` (or plain ```) fences that the model may add
    despite being told not to, then parse and return the Python object.

    Why the rstrip("`"): re.sub strips the opening fence; if the model
    puts a bare ``` at the end with no newline before it, the rstrip
    catches the trailing backticks the regex missed.
    """
    text = re.sub(r"```(?:json)?\s*", "", text).strip().rstrip("`")
    return json.loads(text)


def make_plan(goal: str) -> dict:
    """
    Ask the LLM to decompose `goal` into 4-7 sequential steps.
    Writes the resulting plan to plan.json and returns the plan dict.
    """
    resp = call_llm([
        {"role": "system", "content": DECOMPOSER_PROMPT},
        {"role": "user",   "content": f"Goal: {goal}"},
    ])  # no tools= — forces text-only response

    raw = resp.choices[0].message.content
    
    try:
        steps_raw = extract_json(raw)
    except Exception as e:
        print(f"[WARN] Failed to parse JSON, recovering... Error: {e}")
        steps_raw = [{"id": 1, "task": raw.strip()[:200]}] # Hard fallback

    # Defensive parsing 1: If the LLM wrapped the array in a dict (e.g., {"steps": [...]})
    if isinstance(steps_raw, dict):
        for val in steps_raw.values():
            if isinstance(val, list):
                steps_raw = val
                break
        else:
            steps_raw = [steps_raw] # Wrap the dict in a list if no internal list found

    # Defensive parsing 2: Ensure every item is a dictionary with an id and task
    clean_steps = []
    for i, s in enumerate(steps_raw, 1):
        if isinstance(s, dict):
            clean_steps.append({
                "id": s.get("id", i),
                "task": s.get("task", str(s)),
                "status": "pending",
                "result": None,
            })
        else:
            # If 's' is just a plain string
            clean_steps.append({
                "id": i,
                "task": str(s),
                "status": "pending",
                "result": None,
            })

    plan = {
        "goal": goal,
        "status": "in_progress",
        "current_step": 1,
        "steps": clean_steps,
    }
    save_plan(plan)
    return plan


# ─────────────────────────────────────────────────────────────────
# 7. CONTEXT BUILDER — build_step_context   (Phase 4)
# ─────────────────────────────────────────────────────────────────

def build_step_context(plan: dict, step: dict) -> list:
    """
    Build the messages list for execute_step's inner ReAct loop.

    Token cost is O(1) per step — only three things ever go in:
      1. System persona (constant size)
      2. The overall goal (constant size)
      3. At most ONE previous step's result, capped at 300 chars

    Why just one step back?  Accumulating all previous results would
    make cost O(n) and blow TPM on long plans.  One step back is
    enough for the model to maintain continuity (e.g. "use the URL
    you found in the previous step") without runaway token growth.

    The 300-char hard cap on previous result:
      A step result could be thousands of characters (e.g. a full page
      of scraped text).  We only want the gist for continuity, not the
      raw data — execute_step will re-fetch if it needs more.
    """
    messages = [
        {"role": "system", "content": PLANNER_PERSONA},
        {"role": "user",   "content": f"Overall goal: {plan['goal']}"},
    ]

    # Look one step back — skip if first step or previous result is None
    prev = get_step(plan, step["id"] - 1)
    if prev and prev["result"]:
        summary = prev["result"][:300]   # hard cap — gist only
        messages.append({
            "role":    "user",
            "content": f"Context from previous step: {summary}",
        })

    messages.append({
        "role":    "user",
        "content": f"Your task for this step:\n{step['task']}",
    })

    return messages


# ─────────────────────────────────────────────────────────────────
# 8. EXECUTOR — execute_step   (Phase 3 — stub)
# ─────────────────────────────────────────────────────────────────

# ─────────────────────────────────────────────────────────────────
# 8. EXECUTOR — execute_step   (Phase 5)
# ─────────────────────────────────────────────────────────────────

def execute_step(plan: dict, step: dict) -> str:
    """
    Run the inner ReAct loop for one step. Returns the final text result.

    ReAct pattern (Reason + Act):
      while True:
        call LLM with tools available
        if model emits tool_calls → dispatch each, feed results back, loop
        else (plain text)         → return that text as the step result

    Why this terminates: every tool call gives the model new information.
    Eventually it either has enough to answer or hits the context limit.
    In practice, 1-3 tool calls per step is typical.

    Crash-safety guarantee:
      step["status"] = "in_progress" is written to disk BEFORE the first
      Groq call. If the process dies mid-step, on restart run() finds
      the step still "in_progress" and re-executes it from scratch.
      Tool calls are cheap enough that re-running a step is acceptable.
      Do NOT mark "done" here — run() owns that transition.

    fn_args parsing:
      tc.function.arguments is a JSON string (sometimes empty string "").
      We parse it, then guard with isinstance(parsed, dict) because a
      badly-behaved model could return a non-dict JSON value (e.g. null).
    """
    # ── Crash-safety flush ───────────────────────────────────────
    step["status"] = "in_progress"
    save_plan(plan)

    messages = build_step_context(plan, step)

    while True:
        resp = call_llm(messages, tools=tools)
        msg  = resp.choices[0].message
        messages.append(msg)   # Groq SDK objects are accepted back in messages

        if msg.tool_calls:
            for tc in msg.tool_calls:
                fn_name = tc.function.name

                # Parse args — guard against empty string and non-dict JSON
                fn_args = {}
                if tc.function.arguments:
                    parsed = json.loads(tc.function.arguments)
                    if isinstance(parsed, dict):
                        fn_args = parsed

                print(f"  [tool: {fn_name}({fn_args})]", end=" → ", flush=True)
                result = available_tools[fn_name](**fn_args)
                print(str(result)[:80] + "…")

                # Feed tool result back — role="tool" + tool_call_id is
                # required by the OpenAI/Groq function-calling protocol
                messages.append({
                    "tool_call_id": tc.id,
                    "role":         "tool",
                    "name":         fn_name,
                    "content":      str(result),
                })
            # Loop: model sees the tool result and decides what to do next

        else:
            return msg.content   # terminal: model produced a text answer


# ─────────────────────────────────────────────────────────────────
# 9. OUTER LOOP — run   (Phase 6)
# ─────────────────────────────────────────────────────────────────

def run():
    """
    Top-level state-machine driver. Never returns until the plan is done
    or the user exits (Ctrl-C / empty goal input).

    State transitions per iteration:
      load plan
        ├─ no plan       → ask for goal → make_plan() → show steps
        └─ existing plan → report progress (resume mode)
      while pending steps exist:
          pick first non-done step
          execute_step()  → marks step in_progress on disk before first LLM call
          store result, mark done, advance current_step, save_plan()
      all done → mark plan status="done", print summary, exit

    Resume behaviour:
      Any step still "in_progress" (crash during execute_step) is treated
      as pending — pending = [s for s ... if s["status"] != "done"]
      That step will be re-executed from scratch, which is correct and safe:
      tool calls are idempotent (search / fetch) and the step result has not
      yet been written to the plan.

    The save_plan() call AFTER execute_step() is the only place a step
    transitions to "done". execute_step() must never do that itself.
    """
    plan = load_plan()

    if not plan or "steps" not in plan:
        # ── Fresh run: ask for goal and decompose ─────────────────
        goal = input("Goal: ").strip()
        if not goal:
            print("No goal given. Exiting.")
            return
        print("\n[VECTOR] Decomposing goal into steps…")
        plan = make_plan(goal)
        print(f"[VECTOR] Plan written — {len(plan['steps'])} steps:\n")
        for s in plan["steps"]:
            print(f"  {s['id']}. {s['task']}")
        print()
    else:
        # ── Resume run: report where we left off ──────────────────
        done_count = sum(1 for s in plan["steps"] if s["status"] == "done")
        in_prog    = [s for s in plan["steps"] if s["status"] == "in_progress"]
        print(f"\n[VECTOR] Resuming — goal: {plan['goal']!r}")
        print(f"         {done_count}/{len(plan['steps'])} steps done", end="")
        if in_prog:
            print(f"  |  re-running step {in_prog[0]['id']} (was in_progress at last crash)", end="")
        print()

    # ── Main execution loop ───────────────────────────────────────
    while True:
        # Includes "in_progress" steps — they need to be re-executed
        pending = [s for s in plan["steps"] if s["status"] != "done"]

        if not pending:
            plan["status"] = "done"
            save_plan(plan)
            print("\n[VECTOR] All steps complete.\n")
            print("─" * 55)
            for s in plan["steps"]:
                print(f"  [{s['id']}] {s['task']}")
                if s["result"]:
                    # Print first 120 chars of the result as a preview
                    preview = s["result"][:120].replace("\n", " ")
                    suffix  = "…" if len(s["result"]) > 120 else ""
                    print(f"       → {preview}{suffix}")
            print("─" * 55)
            break

        step = pending[0]
        total = len(plan["steps"])
        print(f"\n[VECTOR] → Step {step['id']}/{total}: {step['task']}")

        result = execute_step(plan, step)   # inner ReAct loop; may call tools

        # ── Commit result — only run() owns the "done" transition ─
        step["result"]       = result
        step["status"]       = "done"
        plan["current_step"] = step["id"] + 1
        save_plan(plan)   # durable checkpoint: crash after this is fully safe

        print(f"[VECTOR] ✓ Step {step['id']} done.")


# ─────────────────────────────────────────────────────────────────
# 10. PHASE 1 TEST — run this now, before touching anything else
#     Expected output documented below each assertion.
# ─────────────────────────────────────────────────────────────────

def test_state_layer():
    print("=" * 55)
    print("PHASE 1 TEST — State Layer")
    print("=" * 55)

    # ── Test A: save then load round-trip ────────────────────────
    dummy_plan = {
        "goal": "Learn Phase 1 of the planner agent",
        "status": "in_progress",
        "current_step": 1,
        "steps": [
            {"id": 1, "task": "Write load_plan and save_plan",
             "status": "done",   "result": "Functions written and tested."},
            {"id": 2, "task": "Write get_step helper",
             "status": "pending", "result": None},
            {"id": 3, "task": "Run the full state-layer test",
             "status": "pending", "result": None},
        ]
    }

    save_plan(dummy_plan)
    loaded = load_plan()

    assert loaded == dummy_plan, "FAIL: round-trip mismatch"
    print("✓  A  save_plan → load_plan round-trip:  PASS")

    # ── Test B: get_step hits ─────────────────────────────────────
    step1 = get_step(loaded, 1)
    assert step1 is not None,          "FAIL: step 1 not found"
    assert step1["status"] == "done",  "FAIL: step 1 status wrong"
    assert step1["task"] == "Write load_plan and save_plan", "FAIL: task text wrong"
    print("✓  B  get_step(plan, 1) — known id:      PASS")

    step3 = get_step(loaded, 3)
    assert step3 is not None,            "FAIL: step 3 not found"
    assert step3["result"] is None,      "FAIL: step 3 result should be None"
    print("✓  C  get_step(plan, 3) — last step:     PASS")

    # ── Test C: get_step miss ─────────────────────────────────────
    missing = get_step(loaded, 99)
    assert missing is None, "FAIL: out-of-range id should return None"
    print("✓  D  get_step(plan, 99) — bad id → None: PASS")

    # ── Test D: get_step on edge case (step before first) ────────
    step0 = get_step(loaded, 0)
    assert step0 is None, "FAIL: id=0 should return None"
    print("✓  E  get_step(plan, 0)  — id=0  → None: PASS")

    # ── Test E: load_plan on a corrupt file ───────────────────────
    with open(PLAN_FILE, "w") as f:
        f.write("{ this is not valid JSON !!!")      # deliberately corrupt
    result = load_plan()
    assert result == {}, "FAIL: corrupt file should return {}"
    print("✓  F  load_plan on corrupt file → {}:    PASS")

    # ── Test F: load_plan when file doesn't exist ─────────────────
    os.remove(PLAN_FILE)
    result = load_plan()
    assert result == {}, "FAIL: missing file should return {}"
    print("✓  G  load_plan when file absent  → {}:  PASS")

    # ── Test G: atomic write — .tmp file must not linger ─────────
    save_plan(dummy_plan)  # write a clean plan back
    assert not os.path.exists(PLAN_FILE + ".tmp"), \
        "FAIL: .tmp file still present after save_plan"
    print("✓  H  atomic write — no stale .tmp file:  PASS")

    # ── Test H: mutate in memory → save → confirm on disk ────────
    loaded2 = load_plan()
    loaded2["steps"][1]["status"] = "done"
    loaded2["steps"][1]["result"] = "get_step written and verified."
    loaded2["current_step"] = 3
    save_plan(loaded2)

    reloaded = load_plan()
    assert reloaded["steps"][1]["status"] == "done", \
        "FAIL: mutation not persisted"
    assert reloaded["current_step"] == 3, \
        "FAIL: current_step not updated"
    print("✓  I  mutate → save → reload persists:   PASS")

    print()
    print("All Phase 1 tests passed.")
    print(f"Final plan.json on disk:\n")
    print(json.dumps(reloaded, indent=2))
    print("=" * 55)


# ─────────────────────────────────────────────────────────────────
# 11. PHASE 2 TEST — call_llm backoff, without touching real API
#     Strategy: patch RateLimitError in THIS module's namespace so
#     the except clause catches our fake class, and patch time.sleep
#     so tests run in milliseconds.
# ─────────────────────────────────────────────────────────────────

def test_call_llm():
    from unittest.mock import MagicMock, patch
    import capstone as mod   # self-import so patch.object targets the right namespace

    print("=" * 55)
    print("PHASE 2 TEST — call_llm / 429 backoff")
    print("=" * 55)

    # ── Fake exception that mimics RateLimitError's shape ────────
    # retry_after=None  →  no Retry-After header (test backoff path)
    # retry_after=N     →  Retry-After: N header (test header path)
    class FakeRateLimitError(Exception):
        def __init__(self, retry_after=None):
            self.response = MagicMock()
            self.response.headers = (
                {"Retry-After": str(retry_after)} if retry_after is not None else {}
            )

    fake_ok = MagicMock()  # stands in for a successful Groq response

    # ── Helper: build a wired mock client ────────────────────────
    def make_mock_client(side_effects):
        """
        side_effects: list passed to create().side_effect
          - FakeRateLimitError() entries → 429
          - fake_ok                      → success
        """
        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = side_effects
        return mock_client

    # ─────────────────────────────────────────────────────────────
    # Test A — success on first try
    # ─────────────────────────────────────────────────────────────
    with patch.object(mod, "RateLimitError", FakeRateLimitError), \
         patch.object(mod, "get_client", return_value=make_mock_client([fake_ok])), \
         patch("time.sleep") as mock_sleep:
        result = mod.call_llm([{"role": "user", "content": "hi"}])

    assert result is fake_ok,          "FAIL A: should return the response"
    assert mock_sleep.call_count == 0, "FAIL A: no sleep on first-try success"
    print("✓  A  success on first try — 0 sleeps")

    # ─────────────────────────────────────────────────────────────
    # Test B — one 429 then success → sleep 2s
    # ─────────────────────────────────────────────────────────────
    with patch.object(mod, "RateLimitError", FakeRateLimitError), \
         patch.object(mod, "get_client",
                      return_value=make_mock_client([FakeRateLimitError(), fake_ok])), \
         patch("time.sleep") as mock_sleep:
        result = mod.call_llm([{"role": "user", "content": "hi"}])

    assert result is fake_ok,             "FAIL B: should eventually return response"
    assert mock_sleep.call_count == 1,    "FAIL B: exactly one sleep"
    assert mock_sleep.call_args[0][0] == 2, \
        f"FAIL B: first sleep should be 2s, got {mock_sleep.call_args[0][0]}"
    print("✓  B  1 rate-limit → sleep 2s → success")

    # ─────────────────────────────────────────────────────────────
    # Test C — three 429s then success → exponential: 2, 4, 8
    # ─────────────────────────────────────────────────────────────
    with patch.object(mod, "RateLimitError", FakeRateLimitError), \
         patch.object(mod, "get_client", return_value=make_mock_client([
             FakeRateLimitError(), FakeRateLimitError(), FakeRateLimitError(), fake_ok
         ])), \
         patch("time.sleep") as mock_sleep:
        result = mod.call_llm([{"role": "user", "content": "hi"}])

    sleep_vals = [c[0][0] for c in mock_sleep.call_args_list]
    assert result is fake_ok,               "FAIL C: should return response"
    assert sleep_vals == [2, 4, 8], \
        f"FAIL C: expected [2, 4, 8], got {sleep_vals}"
    print(f"✓  C  3 rate-limits → sleeps {sleep_vals} (exponential confirmed)")

    # ─────────────────────────────────────────────────────────────
    # Test D — exhausted retries re-raises, never returns
    # ─────────────────────────────────────────────────────────────
    mock_client = make_mock_client([FakeRateLimitError()] * 10)  # always fails
    raised = False
    with patch.object(mod, "RateLimitError", FakeRateLimitError), \
         patch.object(mod, "get_client", return_value=mock_client), \
         patch("time.sleep"):
        try:
            mod.call_llm([{"role": "user", "content": "hi"}], max_retries=3)
        except FakeRateLimitError:
            raised = True

    assert raised, "FAIL D: should re-raise after exhausting retries"
    assert mock_client.chat.completions.create.call_count == 3, \
        f"FAIL D: expected 3 attempts, got {mock_client.chat.completions.create.call_count}"
    print("✓  D  max_retries=3 exhausted → re-raises after exactly 3 attempts")

    # ─────────────────────────────────────────────────────────────
    # Test E — tools=None must NOT set tool_choice
    # ─────────────────────────────────────────────────────────────
    mock_client = make_mock_client([fake_ok])
    with patch.object(mod, "RateLimitError", FakeRateLimitError), \
         patch.object(mod, "get_client", return_value=mock_client), \
         patch("time.sleep"):
        mod.call_llm([{"role": "user", "content": "hi"}], tools=None)

    kwargs = mock_client.chat.completions.create.call_args[1]
    assert kwargs.get("tool_choice") is None, \
        f"FAIL E: tools=None should give tool_choice=None, got {kwargs.get('tool_choice')}"
    print("✓  E  tools=None  → tool_choice=None  (no accidental tool forcing)")

    # ─────────────────────────────────────────────────────────────
    # Test F — tools=[...] must set tool_choice="auto"
    # ─────────────────────────────────────────────────────────────
    mock_client = make_mock_client([fake_ok])
    fake_tools  = [{"type": "function", "function": {"name": "search_the_web"}}]
    with patch.object(mod, "RateLimitError", FakeRateLimitError), \
         patch.object(mod, "get_client", return_value=mock_client), \
         patch("time.sleep"):
        mod.call_llm([{"role": "user", "content": "hi"}], tools=fake_tools)

    kwargs = mock_client.chat.completions.create.call_args[1]
    assert kwargs.get("tool_choice") == "auto", \
        f"FAIL F: tools=[...] should give tool_choice='auto', got {kwargs.get('tool_choice')}"
    print("✓  F  tools=[...] → tool_choice='auto'  (model chooses when to call)")

    # ─────────────────────────────────────────────────────────────
    # Test G — Retry-After header overrides backoff delay
    # ─────────────────────────────────────────────────────────────
    with patch.object(mod, "RateLimitError", FakeRateLimitError), \
         patch.object(mod, "get_client", return_value=make_mock_client([
             FakeRateLimitError(retry_after=7), fake_ok
         ])), \
         patch("time.sleep") as mock_sleep:
        mod.call_llm([{"role": "user", "content": "hi"}])

    actual = mock_sleep.call_args[0][0]
    assert actual == 7.0, \
        f"FAIL G: Retry-After: 7 should sleep 7s, got {actual}s"
    print(f"✓  G  Retry-After: 7 header → sleeps exactly 7s (not backoff 2s)")

    # ─────────────────────────────────────────────────────────────
    # Test H — backoff doubles even after a Retry-After sleep
    #          so subsequent headerless errors get correct interval
    # ─────────────────────────────────────────────────────────────
    with patch.object(mod, "RateLimitError", FakeRateLimitError), \
         patch.object(mod, "get_client", return_value=make_mock_client([
             FakeRateLimitError(retry_after=5),  # sleeps 5, advances delay 2→4
             FakeRateLimitError(),               # sleeps 4  (backoff, no header)
             fake_ok,
         ])), \
         patch("time.sleep") as mock_sleep:
        mod.call_llm([{"role": "user", "content": "hi"}])

    sleep_vals = [c[0][0] for c in mock_sleep.call_args_list]
    assert sleep_vals == [5.0, 4.0], \
        f"FAIL H: expected [5.0, 4.0], got {sleep_vals}"
    print(f"✓  H  Retry-After then headerless → sleeps {sleep_vals} "
          f"(backoff advanced correctly)")

    print()
    print("All Phase 2 tests passed.")
    print("=" * 55)


# ─────────────────────────────────────────────────────────────────
# 12. PHASE 3 TEST — extract_json + make_plan (no real API calls)
#     Mocks call_llm so the test runs offline and instantly.
# ─────────────────────────────────────────────────────────────────

def test_make_plan():
    from unittest.mock import MagicMock, patch
    import capstone as mod

    print("=" * 55)
    print("PHASE 3 TEST — extract_json + make_plan")
    print("=" * 55)

    # ── Test A: extract_json — clean JSON, no fences ──────────────
    raw = '[{"id": 1, "task": "Do something"}, {"id": 2, "task": "Do more"}]'
    result = mod.extract_json(raw)
    assert isinstance(result, list),        "FAIL A: should return a list"
    assert result[0]["id"] == 1,            "FAIL A: first item id wrong"
    assert result[1]["task"] == "Do more",  "FAIL A: second item task wrong"
    print("✓  A  extract_json — clean JSON:               PASS")

    # ── Test B: extract_json — strips ```json ... ``` fences ──────
    fenced = '```json\n[{"id": 1, "task": "Step one"}]\n```'
    result = mod.extract_json(fenced)
    assert isinstance(result, list),         "FAIL B: should parse despite fences"
    assert result[0]["task"] == "Step one",  "FAIL B: task content wrong after strip"
    print("✓  B  extract_json — strips ```json fences:    PASS")

    # ── Test C: extract_json — strips plain ``` fences ────────────
    plain_fenced = '```\n[{"id": 1, "task": "Plain"}]\n```'
    result = mod.extract_json(plain_fenced)
    assert result[0]["task"] == "Plain",     "FAIL C: plain fence not stripped"
    print("✓  C  extract_json — strips plain ``` fences:  PASS")

    # ── Test D: make_plan — top-level plan structure ───────────────
    fake_content = (
        '[{"id": 1, "task": "Research the topic"}, '
        ' {"id": 2, "task": "Write outline"}, '
        ' {"id": 3, "task": "Draft content"}]'
    )
    fake_resp = MagicMock()
    fake_resp.choices[0].message.content = fake_content

    with patch.object(mod, "call_llm", return_value=fake_resp):
        plan = mod.make_plan("Write a blog post about Python")

    assert plan["goal"]         == "Write a blog post about Python", "FAIL D: goal wrong"
    assert plan["status"]       == "in_progress",                    "FAIL D: status wrong"
    assert plan["current_step"] == 1,                                "FAIL D: current_step wrong"
    assert len(plan["steps"])   == 3,                                "FAIL D: wrong step count"
    print("✓  D  make_plan — top-level structure:          PASS")

    # ── Test E: make_plan — every step has the correct shape ───────
    for s in plan["steps"]:
        assert "id"     in s and isinstance(s["id"],   int), f"FAIL E: bad id in {s}"
        assert "task"   in s and isinstance(s["task"], str), f"FAIL E: bad task in {s}"
        assert s["status"] == "pending",                      f"FAIL E: step {s['id']} not pending"
        assert s["result"] is None,                           f"FAIL E: step {s['id']} result not None"
    print("✓  E  make_plan — all steps pending, result=None: PASS")

    # ── Test F: make_plan — plan was persisted to disk ─────────────
    on_disk = mod.load_plan()
    assert on_disk["goal"]      == "Write a blog post about Python", "FAIL F: goal not on disk"
    assert len(on_disk["steps"]) == 3,                               "FAIL F: steps not persisted"
    print("✓  F  make_plan — plan.json written to disk:    PASS")

    # ── Test G: make_plan — call_llm called with no tools= ─────────
    fake_resp2 = MagicMock()
    fake_resp2.choices[0].message.content = fake_content
    with patch.object(mod, "call_llm", return_value=fake_resp2) as mock_call:
        mod.make_plan("Any goal")
    _, kwargs = mock_call.call_args
    assert "tools" not in kwargs or kwargs.get("tools") is None, \
        "FAIL G: make_plan must not pass tools= to call_llm"
    print("✓  G  make_plan — call_llm called without tools=: PASS")

    # Cleanup plan.json written during this test
    if os.path.exists(PLAN_FILE):
        os.remove(PLAN_FILE)

    print()
    print("All Phase 3 tests passed.")
    print("=" * 55)


# ─────────────────────────────────────────────────────────────────
# 13. PHASE 4 TEST — tools schema + build_step_context
#     All offline — no Groq calls, no network.
# ─────────────────────────────────────────────────────────────────

def test_build_step_context():
    import capstone as mod

    print("=" * 55)
    print("PHASE 4 TEST — tools schema + build_step_context")
    print("=" * 55)

    # ── Shared fixture ────────────────────────────────────────────
    plan = {
        "goal": "Research quantum computing",
        "status": "in_progress",
        "current_step": 2,
        "steps": [
            {"id": 1, "task": "Find overview articles",
             "status": "done",
             "result": "Found 3 articles at arxiv.org covering qubits and superposition."},
            {"id": 2, "task": "Summarise key concepts",
             "status": "pending", "result": None},
            {"id": 3, "task": "Write a one-page summary",
             "status": "pending", "result": None},
        ],
    }

    # ── Test A: tools schema — both entries present with correct names ──
    names = {t["function"]["name"] for t in mod.tools}
    assert "search_the_web" in names, "FAIL A: search_the_web missing from tools schema"
    assert "open_page"      in names, "FAIL A: open_page missing from tools schema"
    print("✓  A  tools schema — both functions declared:    PASS")

    # ── Test B: tools schema — each entry has required fields ──────
    for t in mod.tools:
        fn = t["function"]
        assert "name"        in fn,                 f"FAIL B: 'name' missing in {fn}"
        assert "description" in fn,                 f"FAIL B: 'description' missing in {fn}"
        assert "parameters"  in fn,                 f"FAIL B: 'parameters' missing in {fn}"
        assert fn["parameters"]["type"] == "object",f"FAIL B: parameters type wrong in {fn['name']}"
    print("✓  B  tools schema — all required fields present: PASS")

    # ── Test C: available_tools keys match schema names ─────────────
    schema_names = {t["function"]["name"] for t in mod.tools}
    assert schema_names == set(mod.available_tools.keys()), \
        f"FAIL C: schema names {schema_names} != dispatch keys {set(mod.available_tools.keys())}"
    print("✓  C  available_tools keys match schema names:   PASS")

    # ── Test D: available_tools values are callable ─────────────────
    for name, fn in mod.available_tools.items():
        assert callable(fn), f"FAIL D: available_tools['{name}'] is not callable"
    print("✓  D  available_tools values are callable:       PASS")

    # ── Test E: first step — no previous context in messages ───────
    step1 = plan["steps"][0]   # id=1, first step
    msgs  = mod.build_step_context(plan, step1)
    roles = [m["role"] for m in msgs]
    assert roles[0] == "system",                "FAIL E: first message must be system"
    assert roles.count("user") >= 2,            "FAIL E: need at least goal + task user msgs"
    contents = [m["content"] for m in msgs]
    assert not any("Context from previous" in c for c in contents), \
        "FAIL E: step 1 must not include previous-step context"
    print("✓  E  step 1 — no previous-step context injected: PASS")

    # ── Test F: middle step — previous result injected ─────────────
    step2 = plan["steps"][1]   # id=2, previous step has a result
    msgs  = mod.build_step_context(plan, step2)
    contents = [m["content"] for m in msgs]
    assert any("Context from previous" in c for c in contents), \
        "FAIL F: step 2 should include previous-step context"
    print("✓  F  step 2 — previous result injected:          PASS")

    # ── Test G: previous result is capped at 300 chars ─────────────
    long_result_plan = {
        "goal": "Test goal",
        "steps": [
            {"id": 1, "task": "Step one", "status": "done",
             "result": "x" * 500},   # 500 chars — should be capped to 300
            {"id": 2, "task": "Step two", "status": "pending", "result": None},
        ],
    }
    step2_long = long_result_plan["steps"][1]
    msgs = mod.build_step_context(long_result_plan, step2_long)
    ctx_msg = next(m for m in msgs if "Context from previous" in m["content"])
    injected = ctx_msg["content"].replace("Context from previous step: ", "")
    assert len(injected) <= 300, \
        f"FAIL G: injected context is {len(injected)} chars, expected ≤ 300"
    print("✓  G  previous result capped at 300 chars:        PASS")

    # ── Test H: previous step result=None — context skipped ────────
    plan_no_result = {
        "goal": "Test goal",
        "steps": [
            {"id": 1, "task": "Step one", "status": "done", "result": None},
            {"id": 2, "task": "Step two", "status": "pending", "result": None},
        ],
    }
    step2_none = plan_no_result["steps"][1]
    msgs = mod.build_step_context(plan_no_result, step2_none)
    contents = [m["content"] for m in msgs]
    assert not any("Context from previous" in c for c in contents), \
        "FAIL H: result=None must not inject context"
    print("✓  H  previous result=None — context skipped:     PASS")

    # ── Test I: task text appears in final user message ─────────────
    step2 = plan["steps"][1]
    msgs = mod.build_step_context(plan, step2)
    last_user = [m for m in msgs if m["role"] == "user"][-1]
    assert step2["task"] in last_user["content"], \
        "FAIL I: step task text must appear in last user message"
    print("✓  I  step task text in final user message:       PASS")

    # ── Test J: system message content is PLANNER_PERSONA ──────────
    step1 = plan["steps"][0]
    msgs  = mod.build_step_context(plan, step1)
    assert msgs[0]["content"] == mod.PLANNER_PERSONA, \
        "FAIL J: system message must be PLANNER_PERSONA"
    print("✓  J  system message is PLANNER_PERSONA:          PASS")

    print()
    print("All Phase 4 tests passed.")
    print("=" * 55)


# ─────────────────────────────────────────────────────────────────
# 14. PHASE 5 TEST — execute_step / inner ReAct loop
#     All mocked — no Groq calls, no network.
# ─────────────────────────────────────────────────────────────────

def test_execute_step():
    from unittest.mock import MagicMock, patch
    import capstone as mod

    print("=" * 55)
    print("PHASE 5 TEST — execute_step / inner ReAct loop")
    print("=" * 55)

    # ── Shared helpers ────────────────────────────────────────────
    def fresh_plan():
        """New plan dict each time so mutations don't bleed between tests."""
        return {
            "goal": "Research Python",
            "status": "in_progress",
            "current_step": 1,
            "steps": [
                {"id": 1, "task": "Find Python docs URL",
                 "status": "pending", "result": None},
            ],
        }

    def make_text_resp(content):
        """Groq response mock whose message has no tool calls."""
        msg = MagicMock()
        msg.tool_calls = []    # empty list → falsy → terminal branch
        msg.content    = content
        resp = MagicMock()
        resp.choices[0].message = msg
        return resp

    def make_tool_resp(fn_name, fn_args_json, call_id="call_t001"):
        """Groq response mock whose message requests one tool call."""
        tc = MagicMock()
        tc.id                  = call_id
        tc.function.name       = fn_name
        tc.function.arguments  = fn_args_json
        msg = MagicMock()
        msg.tool_calls = [tc]   # truthy → dispatch branch
        msg.content    = None
        resp = MagicMock()
        resp.choices[0].message = msg
        return resp

    fake_tools = {"search_the_web": MagicMock(return_value="sr"),
                  "open_page":      MagicMock(return_value="pg")}

    # ── Test A: immediate text response (no tool calls) ────────────
    plan = fresh_plan()
    step = plan["steps"][0]
    with patch.object(mod, "call_llm", return_value=make_text_resp("python.org")), \
         patch.object(mod, "available_tools", fake_tools), \
         patch.object(mod, "save_plan"):
        result = mod.execute_step(plan, step)

    assert result == "python.org", f"FAIL A: got {result!r}"
    print("✓  A  immediate text → returns content:            PASS")

    # ── Test B: crash-safety — in_progress saved BEFORE first LLM call
    plan = fresh_plan()
    step = plan["steps"][0]
    call_order = []

    def track_save(p):
        call_order.append(("save", p["steps"][0]["status"]))

    def track_llm(msgs, **kwargs):
        call_order.append(("llm", None))
        return make_text_resp("done")

    with patch.object(mod, "save_plan", side_effect=track_save), \
         patch.object(mod, "call_llm", side_effect=track_llm), \
         patch.object(mod, "available_tools", fake_tools):
        mod.execute_step(plan, step)

    assert call_order[0] == ("save", "in_progress"), \
        f"FAIL B: first event must be save(in_progress), got {call_order[0]}"
    assert call_order[1][0] == "llm", \
        f"FAIL B: second event must be llm call, got {call_order[1]}"
    print("✓  B  in_progress flushed to disk before LLM call: PASS")

    # ── Test C: one tool call → tool executed → text response ──────
    plan = fresh_plan()
    step = plan["steps"][0]
    mock_search = MagicMock(return_value="search results")

    with patch.object(mod, "call_llm",
                      side_effect=[make_tool_resp("search_the_web", '{"query": "Python docs"}'),
                                   make_text_resp("Found at python.org")]), \
         patch.object(mod, "available_tools",
                      {"search_the_web": mock_search, "open_page": MagicMock()}), \
         patch.object(mod, "save_plan"):
        result = mod.execute_step(plan, step)

    assert result == "Found at python.org",       f"FAIL C: got {result!r}"
    mock_search.assert_called_once_with(query="Python docs")
    print("✓  C  tool call → executed → text response:        PASS")

    # ── Test D: tool result fed back with role='tool' ───────────────
    plan = fresh_plan()
    step = plan["steps"][0]
    msgs_on_second_call = []
    n_calls = [0]

    def capture(msgs, **kwargs):
        n_calls[0] += 1
        if n_calls[0] == 1:
            return make_tool_resp("search_the_web", '{"query": "q"}')
        msgs_on_second_call.extend(msgs)   # capture 2nd-call messages
        return make_text_resp("done")

    with patch.object(mod, "call_llm", side_effect=capture), \
         patch.object(mod, "available_tools",
                      {"search_the_web": MagicMock(return_value="tool output"),
                       "open_page":      MagicMock()}), \
         patch.object(mod, "save_plan"):
        mod.execute_step(plan, step)

    tool_msgs = [m for m in msgs_on_second_call
                 if isinstance(m, dict) and m.get("role") == "tool"]
    assert len(tool_msgs) == 1,                     "FAIL D: expected 1 tool-role message"
    assert tool_msgs[0]["content"]      == "tool output", \
        f"FAIL D: wrong tool content: {tool_msgs[0]['content']!r}"
    assert tool_msgs[0]["tool_call_id"] == "call_t001",   "FAIL D: wrong tool_call_id"
    assert tool_msgs[0]["name"]         == "search_the_web", "FAIL D: wrong tool name"
    print("✓  D  tool result appended with role='tool':        PASS")

    # ── Test E: call_llm called with tools= (not None) ─────────────
    plan = fresh_plan()
    step = plan["steps"][0]
    with patch.object(mod, "call_llm", return_value=make_text_resp("ok")) as mock_llm, \
         patch.object(mod, "available_tools", fake_tools), \
         patch.object(mod, "save_plan"):
        mod.execute_step(plan, step)

    _, kwargs = mock_llm.call_args
    assert kwargs.get("tools") is mod.tools, \
        f"FAIL E: tools kwarg should be mod.tools, got {kwargs.get('tools')!r}"
    print("✓  E  call_llm receives tools=mod.tools:            PASS")

    # ── Test F: two tool calls in one turn — both dispatched ───────
    plan = fresh_plan()
    step = plan["steps"][0]
    tc1 = MagicMock(); tc1.id = "c1"; tc1.function.name = "search_the_web"
    tc1.function.arguments = '{"query": "q1"}'
    tc2 = MagicMock(); tc2.id = "c2"; tc2.function.name = "open_page"
    tc2.function.arguments = '{"url": "https://x.com"}'
    multi_msg = MagicMock()
    multi_msg.tool_calls = [tc1, tc2]
    multi_msg.content    = None
    multi_resp = MagicMock()
    multi_resp.choices[0].message = multi_msg

    mock_s = MagicMock(return_value="search out")
    mock_o = MagicMock(return_value="page out")
    with patch.object(mod, "call_llm", side_effect=[multi_resp, make_text_resp("all done")]), \
         patch.object(mod, "available_tools", {"search_the_web": mock_s, "open_page": mock_o}), \
         patch.object(mod, "save_plan"):
        result = mod.execute_step(plan, step)

    assert result == "all done",                           "FAIL F: wrong final result"
    mock_s.assert_called_once_with(query="q1")
    mock_o.assert_called_once_with(url="https://x.com")
    print("✓  F  two tool calls in one turn — both dispatched: PASS")

    # ── Test G: empty arguments string → fn_args defaults to {} ───
    plan = fresh_plan()
    step = plan["steps"][0]
    mock_fn = MagicMock(return_value="ok")
    with patch.object(mod, "call_llm",
                      side_effect=[make_tool_resp("search_the_web", ""),
                                   make_text_resp("done")]), \
         patch.object(mod, "available_tools",
                      {"search_the_web": mock_fn, "open_page": MagicMock()}), \
         patch.object(mod, "save_plan"):
        mod.execute_step(plan, step)

    mock_fn.assert_called_once_with()   # called with no kwargs
    print("✓  G  empty arguments string → called with no args: PASS")

    print()
    print("All Phase 5 tests passed.")
    print("=" * 55)


if __name__ == "__main__":
    import sys
    if "--test" in sys.argv:
        # Run the full offline test suite for phases 1-5.
        # Usage: python capstone.py --test
        test_state_layer()
        print()
        test_call_llm()
        print()
        test_make_plan()
        print()
        test_build_step_context()
        print()
        test_execute_step()
    else:
        # Normal entry point: run the planner agent.
        # Usage: python capstone.py
        run()