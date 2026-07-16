"""Capstone — The Planner Agent.

State-driven orchestration. You hand the agent one big goal. It decomposes the
goal into ordered sub-tasks, writes them to ``plan.json``, then works through
them one step at a time: read state from disk, execute the next pending step,
write the result back, advance. Kill it mid-run (Ctrl-C) and start it again --
it resumes from exactly where it left off.

    plan.json is the agent's brain. The Python process is disposable.

Four organs from the term, wired into one creature:
  * Voice  -- Captain Vera, a terse starship-navigator project manager (persona).
  * Hands  -- real tools a step may call: web_search, save_file.
  * Brain  -- a reason -> act -> observe loop that runs *inside* one step.
  * Self   -- plan.json surviving a full restart.
  * New    -- task decomposition + resumable, state-driven orchestration.
"""

import json
import os
import time
from pathlib import Path

from dotenv import find_dotenv, load_dotenv
from groq import Groq

try:  # RateLimitError moved around between groq SDK versions; degrade gracefully.
    from groq import RateLimitError
except ImportError:  # pragma: no cover - depends on installed SDK version
    RateLimitError = Exception

# Playwright is only needed if a step actually calls web_search. Import lazily
# so the agent still runs (and stays resumable) on a machine without it.
try:
    from playwright.sync_api import TimeoutError as PlaywrightTimeout
    from playwright.sync_api import sync_playwright

    _PLAYWRIGHT_OK = True
except ImportError:  # pragma: no cover
    _PLAYWRIGHT_OK = False


MODEL = "llama-3.3-70b-versatile"
BASE_DIR = Path(__file__).resolve().parent
PLAN_FILE = BASE_DIR / "plan.json"
OUTPUT_DIR = BASE_DIR / "outputs"

# --- Voice -----------------------------------------------------------------
PLANNER_PERSONA = (
    "You are Captain Vera, a retired starship navigator turned project manager. "
    "You are terse, decisive, and calm under pressure, and you call the user "
    "'commander'. You break big missions into a clear ordered flight plan and "
    "execute one leg at a time. When a step needs live facts, use web_search; "
    "when a step produces a deliverable worth keeping, use save_file. Do exactly "
    "the one step you are given -- never jump ahead. Answer in character."
)


# ---------------------------------------------------------------------------
# State layer -- plan.json round-trips. Nothing else works without this.
# ---------------------------------------------------------------------------
def load_plan() -> dict:
    """Read plan.json. A missing/blank/corrupt file yields an empty plan."""
    if not PLAN_FILE.exists():
        return {}
    try:
        with PLAN_FILE.open(encoding="utf-8") as file:
            data = json.load(file)
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def save_plan(plan: dict) -> None:
    """Flush the whole plan to disk. Called after *every* state change."""
    with PLAN_FILE.open("w", encoding="utf-8") as file:
        json.dump(plan, file, indent=2)


def get_step(plan: dict, step_id: int):
    """Return the step with the given id, or None."""
    for step in plan.get("steps", []):
        if step["id"] == step_id:
            return step
    return None


def next_pending_step(plan: dict):
    """First step that is not yet done (pending or interrupted in_progress)."""
    for step in plan.get("steps", []):
        if step["status"] != "done":
            return step
    return None


# ---------------------------------------------------------------------------
# Groq survival guide -- every LLM call goes through this.
# ---------------------------------------------------------------------------
def call_llm(client: Groq, messages: list, tools=None, max_retries: int = 5):
    """One Groq call, hardened against HTTP 429 with exponential backoff.

    Doubles the wait each time it is told to slow down (2 -> 4 -> 8 -> 16s).
    Honours a Retry-After hint when the SDK exposes one.
    """
    # Only include tool params when tools exist -- Groq rejects tool_choice=null.
    kwargs = {"model": MODEL, "messages": messages}
    if tools:
        kwargs["tools"] = tools
        kwargs["tool_choice"] = "auto"

    delay = 2
    for attempt in range(max_retries):
        try:
            return client.chat.completions.create(**kwargs)
        except RateLimitError as exc:
            if attempt == max_retries - 1:
                raise
            wait = _retry_after(exc, default=delay)
            print(f"    rate-limited (429). backing off {wait}s...")
            time.sleep(wait)
            delay *= 2
    raise RuntimeError("exhausted retries")


def _retry_after(exc, default: int) -> float:
    """Pull a Retry-After hint off the exception if present; else the default."""
    response = getattr(exc, "response", None)
    if response is not None:
        header = getattr(response, "headers", {}) or {}
        value = header.get("retry-after") or header.get("Retry-After")
        if value:
            try:
                return float(value)
            except ValueError:
                pass
    return default


# ---------------------------------------------------------------------------
# Hands -- real tools a step can call.
# ---------------------------------------------------------------------------
def web_search(query: str) -> str:
    """Search the live web (DuckDuckGo HTML) and return the top results as text."""
    if not _PLAYWRIGHT_OK:
        return "web_search unavailable: playwright is not installed."
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto("https://html.duckduckgo.com/html/", timeout=15000)
            page.fill('input[name="q"]', query)
            page.press('input[name="q"]', "Enter")
            page.wait_for_selector(".result__body", timeout=10000)

            results = []
            for row in page.locator(".result__body").all()[:5]:
                title = row.locator(".result__title").inner_text().strip()
                snippet = row.locator(".result__snippet").inner_text().strip()
                results.append(f"{title}\n{snippet}")
            browser.close()
    except PlaywrightTimeout:
        return "Search timed out. The page may be slow or the layout changed."
    except Exception as exc:  # a failed search must not kill the run
        return f"Search failed: {exc}"
    return "\n\n".join(results) or "No results found."


def save_file(filename: str, content: str) -> str:
    """Write a deliverable to the outputs/ folder and return its path."""
    OUTPUT_DIR.mkdir(exist_ok=True)
    safe_name = Path(filename).name  # strip any path components
    target = OUTPUT_DIR / safe_name
    with target.open("w", encoding="utf-8") as file:
        file.write(content)
    return f"Saved {len(content)} chars to {target.relative_to(BASE_DIR)}"


TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": (
                "Search the live web for current, factual, or real-world "
                "information. Use whenever the step needs data you do not "
                "already know for certain."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "The search query."},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "save_file",
            "description": (
                "Write a text deliverable (report, note, timetable, plan) to "
                "disk so the commander keeps it after the run. Use when a step "
                "produces something worth saving."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "filename": {"type": "string", "description": "e.g. report.md"},
                    "content": {"type": "string", "description": "File contents."},
                },
                "required": ["filename", "content"],
            },
        },
    },
]

AVAILABLE_TOOLS = {
    "web_search": web_search,
    "save_file": save_file,
}


# ---------------------------------------------------------------------------
# make_plan -- one Groq call -> clean JSON list -> pending steps.
# ---------------------------------------------------------------------------
def _extract_json(raw: str) -> str:
    """Strip markdown fences the model sometimes adds despite instructions."""
    text = raw.strip()
    if text.startswith("```"):
        text = text.split("```", 2)[1] if text.count("```") >= 2 else text
        text = text.replace("json", "", 1) if text.lstrip().startswith("json") else text
    return text.strip().strip("`").strip()


def make_plan(client: Groq, goal: str) -> dict:
    """Decompose the goal into an ordered list of tasks and build a fresh plan."""
    messages = [
        {
            "role": "system",
            "content": (
                "You are a planner. Break the user's goal into 3 to 6 ordered, "
                "self-contained sub-tasks. Respond with ONLY a raw JSON array of "
                'strings, no markdown fences, no prose. Example: '
                '["First task", "Second task", "Third task"]'
            ),
        },
        {"role": "user", "content": f"Goal: {goal}"},
    ]
    response = call_llm(client, messages)
    raw = response.choices[0].message.content or "[]"
    try:
        tasks = json.loads(_extract_json(raw))
    except json.JSONDecodeError:
        # Fallback: treat non-empty lines as tasks so a stray format never blocks us.
        tasks = [line.strip("-* \t") for line in raw.splitlines() if line.strip()]

    steps = [
        {"id": i, "task": str(task), "status": "pending", "result": None}
        for i, task in enumerate(tasks, start=1)
        if str(task).strip()
    ]
    return {
        "goal": goal,
        "status": "in_progress",
        "current_step": steps[0]["id"] if steps else 0,
        "steps": steps,
    }


# ---------------------------------------------------------------------------
# Brain -- minimal per-step context + a reason/act/observe loop.
# ---------------------------------------------------------------------------
def build_step_context(plan: dict, step: dict) -> list:
    """Minimal prompt context -- bounded token cost no matter how long the plan.

    Sends only the goal, a short summary of the immediately previous result,
    and the current task. Never the whole steps array or every past result.
    """
    messages = [
        {"role": "system", "content": PLANNER_PERSONA},
        {"role": "user", "content": f"Overall mission: {plan['goal']}"},
    ]
    prev = get_step(plan, step["id"] - 1)
    if prev and prev.get("result"):
        summary = prev["result"][:300]
        messages.append(
            {"role": "user", "content": f"Result of the previous step: {summary}"}
        )
    messages.append(
        {
            "role": "user",
            "content": f"Now do exactly this step, nothing else:\n{step['task']}",
        }
    )
    return messages


def execute_step(client: Groq, plan: dict, step: dict, max_tool_rounds: int = 4) -> str:
    """Run one step through a bounded reason -> act -> observe loop."""
    messages = build_step_context(plan, step)
    for _ in range(max_tool_rounds):
        response = call_llm(client, messages, tools=TOOLS)
        msg = response.choices[0].message
        messages.append(msg)

        if not msg.tool_calls:
            return msg.content or ""

        for call in msg.tool_calls:
            print(f"    [tool] {call.function.name}({call.function.arguments})")
            tool_fn = AVAILABLE_TOOLS.get(call.function.name)
            if tool_fn is None:
                result = f"Unknown tool: {call.function.name}"
            else:
                try:
                    args = json.loads(call.function.arguments or "{}") or {}
                    result = tool_fn(**args)
                except Exception as exc:  # a bad tool call must not kill the step
                    result = f"Tool error: {exc}"
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": call.id,
                    "name": call.function.name,
                    "content": json.dumps(result),
                }
            )

    # Ran out of tool rounds -- force a final plain-text answer.
    messages.append(
        {"role": "user", "content": "Give your final answer for this step now, no tools."}
    )
    response = call_llm(client, messages)
    return response.choices[0].message.content or ""


# ---------------------------------------------------------------------------
# The loop -- stateless, safe to crash and restart.
# ---------------------------------------------------------------------------
def print_plan(plan: dict) -> None:
    print(f"\n  Mission: {plan['goal']}  [{plan['status']}]")
    for step in plan["steps"]:
        mark = {"done": "x", "in_progress": "~", "pending": " "}.get(step["status"], " ")
        print(f"    {step['id']}. [{mark}] {step['task']}")
    print()


def run(client: Groq) -> None:
    plan = load_plan()

    # No plan yet -> ask for a goal and decompose it.
    if not plan.get("steps"):
        goal = input("Captain Vera: What is the mission, commander?\nGoal: ").strip()
        if not goal:
            print("Captain Vera: No goal, no flight. Standing down.")
            return
        print("\nCaptain Vera: Plotting the course...")
        plan = make_plan(client, goal)
        save_plan(plan)
        print_plan(plan)
    else:
        print("Captain Vera: Resuming the mission already on the board.")
        print_plan(plan)

    # Work through steps one at a time, flushing state after each.
    while True:
        step = next_pending_step(plan)
        if step is None:
            plan["status"] = "done"
            save_plan(plan)
            print("Captain Vera: All legs complete, commander. Mission accomplished.")
            print_plan(plan)
            return

        step["status"] = "in_progress"
        plan["current_step"] = step["id"]
        save_plan(plan)  # <-- state on disk BEFORE the risky work

        print(f"  -> Step {step['id']}: {step['task']}")
        result = execute_step(client, plan, step)

        step["result"] = result
        step["status"] = "done"
        save_plan(plan)  # <-- state on disk AFTER; at most one step ever lost
        print(f"     done. {result[:200]}\n")


def main() -> None:
    load_dotenv(find_dotenv(usecwd=True))
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError(
            "Missing GROQ_API_KEY. Put it in a .env file at the project root."
        )
    client = Groq(api_key=api_key)

    print("=== Captain Vera :: The Planner Agent ===")
    print("Hand me a goal. Ctrl-C anytime -- I resume from where I stopped.\n")
    try:
        run(client)
    except KeyboardInterrupt:
        print(
            "\n\nCaptain Vera: Holding position, commander. Progress saved to "
            "plan.json -- run me again to resume."
        )


if __name__ == "__main__":
    main()
