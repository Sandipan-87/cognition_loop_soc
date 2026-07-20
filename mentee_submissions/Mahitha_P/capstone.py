"""
capstone.py  —  The Planner Agent (state-driven orchestration).

Give it one big goal. It decomposes the goal into ordered sub-tasks, writes
them to plan.json, then works through them ONE AT A TIME — reading its state
from disk, executing the next step, writing the result back, advancing.

    plan.json is the agent's brain. The Python process is disposable.

Kill it mid-run (Ctrl-C) and start it again: it resumes from the next
unfinished step, because state is flushed to disk after every single step.

The four organs from the term, all wired in:
    Voice  -> Atlas, a terse project-foreman persona (system prompt).
    Hands  -> real tools a step can call: web search, save_note, current_time.
    Brain  -> a reason -> act -> observe loop INSIDE a single step's execution.
    Self   -> plan.json surviving a full restart (the core of the design).
New idea -> task decomposition + resumable, state-driven orchestration.
"""

import os
import re
import json
import time
import asyncio
import datetime
from dotenv import load_dotenv
from groq import Groq, RateLimitError

load_dotenv()

client = Groq(api_key=os.environ["GROQ_API_KEY"])
MODEL = "llama-3.3-70b-versatile"

PLAN_FILE = "plan.json"
OUTPUT_DIR = "outputs"


# ============================================================
# VOICE  —  the persona Atlas holds while planning and reporting
# ============================================================

PLANNER_PERSONA = (
    "You are Atlas, a terse project foreman. You speak in short, imperative "
    "sentences. No fluff, no pep talk. You break work into concrete steps and "
    "drive them to done. When you finish a step, state the outcome plainly. "
    "When a step needs live facts or an artifact on disk, use your tools; "
    "otherwise just do the thinking and report the result."
)

DECOMPOSER_SYSTEM = (
    "You are Atlas, a project foreman who plans before acting. Break the user's "
    "goal into 3 to 6 ordered, self-contained steps. Each step must be a single "
    "concrete instruction that can be executed on its own, given the result of "
    "the step before it. Respond with ONLY raw JSON — a list of objects of the "
    'form [{"task": "..."}, ...]. No markdown fences, no prose, no numbering.'
)


# ============================================================
# GROQ SURVIVAL  —  every call goes through here (429 backoff)
# ============================================================

def call_llm(messages, tools=None, max_retries=5):
    """One Groq call, hardened against HTTP 429 with exponential backoff.

    Honours the Retry-After header when present, otherwise doubles the delay
    (2 -> 4 -> 8 -> 16 ...). Non-429 errors propagate to the caller.
    """
    # Only include tools/tool_choice when we actually have tools — passing
    # tool_choice=None sends JSON null, which Groq rejects (it wants the
    # parameter omitted, or one of "none"/"auto"/"required").
    kwargs = {"model": MODEL, "messages": messages}
    if tools:
        kwargs["tools"] = tools
        kwargs["tool_choice"] = "auto"

    delay = 2
    for attempt in range(max_retries):
        try:
            return client.chat.completions.create(**kwargs)
        except RateLimitError as e:
            if attempt == max_retries - 1:
                raise
            wait = _retry_after(e) or delay
            print(f"    rate-limited (429). backing off {wait}s...")
            time.sleep(wait)
            delay *= 2
    raise RuntimeError("exhausted retries")


def _retry_after(err):
    """Read a Retry-After value off a RateLimitError, if the header is there."""
    resp = getattr(err, "response", None)
    if resp is not None:
        val = resp.headers.get("retry-after") if hasattr(resp, "headers") else None
        if val:
            try:
                return float(val)
            except ValueError:
                pass
    return None


# ============================================================
# SELF  —  the state layer.  plan.json round-trips to disk.
# ============================================================

def load_plan():
    """Read plan.json, tolerating a missing / empty / half-written file."""
    if not os.path.exists(PLAN_FILE):
        return {}
    with open(PLAN_FILE) as f:
        try:
            data = json.load(f)
        except json.JSONDecodeError:
            return {}
    return data if isinstance(data, dict) else {}


def save_plan(plan):
    """Flush the whole state to disk. Called after EVERY step — the crash guard."""
    with open(PLAN_FILE, "w") as f:
        json.dump(plan, f, indent=2)


def get_step(plan, step_id):
    for s in plan.get("steps", []):
        if s["id"] == step_id:
            return s
    return None


def next_pending(plan):
    """The first step not yet done — this is what makes the plan resumable."""
    for s in plan.get("steps", []):
        if s["status"] != "done":
            return s
    return None


# ============================================================
# BRAIN (part 1)  —  decompose the goal into a plan
# ============================================================

def make_plan(goal):
    """One Groq call -> clean JSON task list -> a fresh plan dict."""
    messages = [
        {"role": "system", "content": DECOMPOSER_SYSTEM},
        {"role": "user", "content": f"Goal: {goal}"},
    ]
    raw = call_llm(messages).choices[0].message.content or "[]"
    tasks = _parse_task_list(raw)

    steps = [
        {"id": i, "task": t, "status": "pending", "result": None}
        for i, t in enumerate(tasks, start=1)
    ]
    return {
        "goal": goal,
        "status": "in_progress",
        "current_step": steps[0]["id"] if steps else 0,
        "steps": steps,
    }


def _parse_task_list(raw):
    """Force a list of task strings out of the model's reply (json_extractor trick)."""
    text = raw.strip()
    text = re.sub(r"^```(?:json)?|```$", "", text, flags=re.MULTILINE).strip()
    match = re.search(r"\[.*\]", text, re.DOTALL)     # grab the JSON array
    if match:
        text = match.group(0)
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        data = []

    tasks = []
    for item in data:
        if isinstance(item, dict) and item.get("task"):
            tasks.append(str(item["task"]).strip())
        elif isinstance(item, str) and item.strip():
            tasks.append(item.strip())
    return tasks


# ============================================================
# HANDS  —  real tools a step can call to DO work
# ============================================================

async def _search_the_web(query):
    from playwright.async_api import async_playwright

    results = []
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        try:
            await page.goto(f"https://html.duckduckgo.com/html/?q={query}", timeout=30000)
            await page.wait_for_selector(".result", timeout=10000)
            for item in (await page.locator(".result").all())[:5]:
                title = await item.locator(".result__title").inner_text()
                link = await item.locator("a").get_attribute("href")
                try:
                    snippet = await item.locator(".result__snippet").inner_text()
                except Exception:
                    snippet = ""
                results.append({"title": title, "link": link, "snippet": snippet})
        except Exception as e:
            results.append({"error": str(e)})
        await browser.close()
    return results


def search_the_web(query):
    return asyncio.run(_search_the_web(query))


def save_note(filename, content):
    """Write text to outputs/<filename> so a step leaves a real artifact on disk."""
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    safe = re.sub(r"[^A-Za-z0-9._-]", "_", filename) or "note.txt"
    path = os.path.join(OUTPUT_DIR, safe)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    return f"Wrote {len(content)} chars to {path}"


def current_time():
    """Current local date and time — for deadlines and scheduling steps."""
    return datetime.datetime.now().strftime("%A, %d %B %Y, %I:%M %p")


TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_the_web",
            "description": "Search the live web for current facts you do not already know.",
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string", "description": "Search query"}},
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "save_note",
            "description": "Save text to a file on disk (an artifact the plan produces).",
            "parameters": {
                "type": "object",
                "properties": {
                    "filename": {"type": "string", "description": "File name, e.g. timetable.txt"},
                    "content": {"type": "string", "description": "The text to write"},
                },
                "required": ["filename", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "current_time",
            "description": "Get the current local date and time for deadlines/scheduling.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
]

available_tools = {
    "search_the_web": lambda query: search_the_web(query),
    "save_note": lambda filename, content: save_note(filename, content),
    "current_time": lambda: current_time(),
}


# ============================================================
# TOOL-CALL RECOVERY  —  Groq/Llama safety net (from Week 4)
# ============================================================
# Llama on Groq usually returns native tool_calls, but sometimes leaks the call
# into text content, or raises `tool_use_failed` on a malformed one. These
# helpers salvage the call so a step never silently loses a tool.

def _safe_json(raw):
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return {}


def parse_text_tool_calls(content):
    """Return [(name, args), ...] recovered from text-leaked tool calls."""
    if not content:
        return []

    py = []
    for m in re.finditer(
        r'\{\s*"name"\s*:\s*"([A-Za-z_]\w*)"\s*,\s*'
        r'"(?:arguments|parameters)"\s*:\s*(\{.*?\})\s*\}',
        content, re.DOTALL,
    ):
        py.append((m.group(1), _safe_json(m.group(2))))
    if py:
        return py

    calls = []
    for m in re.finditer(r"<function[=/]\s*([A-Za-z_]\w*)", content):
        name = m.group(1)
        rest = content[m.end():]
        enders = [rest.find(t) for t in ("</function>", "/>", "<function")]
        enders = [e for e in enders if e != -1]
        block = rest[: min(enders)] if enders else rest[:400]
        jm = re.search(r"\{.*\}", block, re.DOTALL)
        calls.append((name, _safe_json(jm.group(0)) if jm else {}))
    return calls


def _extract_failed_generation(err):
    """Pull raw model output out of a Groq `tool_use_failed` error, else None."""
    candidates = []
    body = getattr(err, "body", None)
    if isinstance(body, dict):
        candidates.append(body)
        if isinstance(body.get("error"), dict):
            candidates.append(body["error"])
    resp = getattr(err, "response", None)
    if resp is not None:
        try:
            data = resp.json()
            if isinstance(data, dict):
                candidates.append(data)
                if isinstance(data.get("error"), dict):
                    candidates.append(data["error"])
        except Exception:
            pass
    for c in candidates:
        if c.get("failed_generation"):
            return c["failed_generation"]
    m = re.search(r"failed_generation['\"]?\s*[:=]\s*['\"](.+?)['\"]\s*[},]", str(err), re.DOTALL)
    return m.group(1) if m else None


# ============================================================
# TPM DISCIPLINE  —  minimal per-step context (bounded token cost)
# ============================================================

def build_step_context(plan, step):
    """Send only what THIS step needs: goal + task + a trimmed previous result.

    Never the full steps array, never every past result — that is what blows
    the Tokens-Per-Minute budget as a plan grows.
    """
    messages = [
        {"role": "system", "content": PLANNER_PERSONA},
        {"role": "user", "content": f"Overall goal: {plan['goal']}"},
    ]
    prev = get_step(plan, step["id"] - 1)
    if prev and prev["result"]:
        summary = prev["result"][:300]
        messages.append({"role": "user", "content": f"Result of the previous step: {summary}"})
    messages.append({"role": "user", "content": f"Now do exactly this step, nothing else:\n{step['task']}"})
    return messages


# ============================================================
# BRAIN (part 2)  —  execute ONE step (reason -> act -> observe)
# ============================================================

def execute_step(plan, step, max_iterations=6):
    """Run a single step to completion, allowing tool use inside it."""
    messages = build_step_context(plan, step)
    synthetic_seq = 0

    for _ in range(max_iterations):
        message = None
        leaked_text = ""
        try:
            message = call_llm(messages, tools=TOOLS).choices[0].message
            if not message.tool_calls:
                leaked_text = message.content or ""
        except Exception as err:
            leaked_text = _extract_failed_generation(err)
            if leaked_text is None:
                raise

        calls = []
        if message is not None and message.tool_calls:
            messages.append(message)
            for tc in message.tool_calls:
                calls.append((tc.id, tc.function.name, _safe_json(tc.function.arguments)))
        else:
            recovered = parse_text_tool_calls(leaked_text)
            if not recovered:
                # No tool call — this text IS the step's result.
                return leaked_text.strip() or "(step produced no output)"
            synthetic = []
            for name, args in recovered:
                synthetic_seq += 1
                cid = f"call_recovered_{synthetic_seq}"
                calls.append((cid, name, args))
                synthetic.append({
                    "id": cid, "type": "function",
                    "function": {"name": name, "arguments": json.dumps(args)},
                })
            messages.append({"role": "assistant", "content": None, "tool_calls": synthetic})

        for call_id, name, args in calls:
            print(f"      tool: {name}({args})")
            if name in available_tools:
                try:
                    result = available_tools[name](**args)
                except Exception as e:
                    result = {"error": str(e)}
            else:
                result = {"error": f"Unknown tool: {name}"}
            messages.append({
                "role": "tool",
                "tool_call_id": call_id,
                "name": name,
                "content": result if isinstance(result, str) else json.dumps(result),
            })

    return "(step hit the tool-iteration cap without a final answer)"


# ============================================================
# THE LOOP  —  stateless, safe to crash and restart
# ============================================================

def print_summary(plan):
    print("\n" + "=" * 60)
    print(f"  GOAL: {plan['goal']}")
    print(f"  STATUS: {plan['status']}")
    print("=" * 60)
    for s in plan["steps"]:
        mark = "x" if s["status"] == "done" else " "
        print(f"  [{mark}] {s['id']}. {s['task']}")
        if s["result"]:
            print(f"        -> {s['result'][:200]}")
    print("=" * 60)


def main():
    print("=" * 60)
    print("  ATLAS — the Planner Agent")
    print("=" * 60)

    plan = load_plan()

    if not plan.get("goal"):
        goal = input("\nGive Atlas a goal: ").strip()
        if not goal:
            print("No goal given. Exiting.")
            return
        print("\nDecomposing goal into a plan...")
        plan = make_plan(goal)
        save_plan(plan)
    elif plan.get("status") == "done":
        print_summary(plan)
        again = input("\nThis plan is finished. Start a NEW goal? (y/N): ").strip().lower()
        if again != "y":
            return
        goal = input("Give Atlas a goal: ").strip()
        if not goal:
            return
        plan = make_plan(goal)
        save_plan(plan)
    else:
        print(f"\nResuming existing plan: {plan['goal']}")

    # The state machine. Reload from disk each turn — plan.json is the truth.
    while True:
        plan = load_plan()
        step = next_pending(plan)

        if step is None:
            plan["status"] = "done"
            save_plan(plan)
            print("\nAll steps complete.")
            print_summary(plan)
            break

        # mark in_progress and flush BEFORE doing work, so a crash mid-step
        # is visible on restart
        step["status"] = "in_progress"
        plan["current_step"] = step["id"]
        save_plan(plan)

        print(f"\n-> Step {step['id']}: {step['task']}")
        result = execute_step(plan, step)

        step["result"] = result
        step["status"] = "done"
        save_plan(plan)                      # <-- the crash guard: state on disk
        print(f"   done: {result[:200]}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nInterrupted. Progress is saved in plan.json — run again to resume.")
