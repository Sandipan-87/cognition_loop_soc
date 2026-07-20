# JOURNEY.md — Mahitha P

## The journey so far

| Week | Organ | What I gave the agent | Files |
|------|-------|-----------------------|-------|
| 1 | Voice | Talk, take on a persona, return clean structured data | `basic_call.py`, `persona_call.py`, `json_extractor.py` |
| 2 | Hands | Call a tool, drive a real browser | `basic_tool.py`, `browser_test.py`, `youtube_autoplay.py` |
| 3 | Brain | Reason → act → observe in a loop, hold a conversation | `research_agent.py`, `chat_agent.py` |
| 4 | Self | A personality, memory that survives a restart, and goals it holds for me | `my_assistant.py` (+ `memory.json`, `goals.json`) |

Week 4, in one line: **Aldric the Archmage** — a wizard-mentor assistant that talks in
character (voice), searches the live web (hands), reasons in a ReAct loop (brain), and
remembers me and my quests across days (self). `remember()` / `recall()` write facts to
`memory.json`; `add_goal()` / `list_goals()` / `complete_goal()` keep a structured quest
log in `goals.json`; both get folded into the system prompt at startup so Aldric walks in
already knowing me.

### One engineering note worth keeping
The memory + quest log are injected into the system prompt on every run. That is fine for
a handful of facts, but it does not scale: a large `memory.json` would eat the context
window and slow every Groq call. The real fix (for the final project) is to stop dumping
everything in and instead *retrieve* only the relevant facts per turn — a `search_memory`
tool, or embeddings + a small vector lookup — so the prompt stays small no matter how much
Aldric has learned.

---

## Looking forward — my final-project seed

### The one-liner
**My final project is an agent that keeps my study & project quests on track for me — a
personal apprenticeship-master ("Aldric the Archmage") who remembers what I'm building,
tracks my goals across days, checks in with what's unfinished, and pulls in live facts when
a task needs them.**

Persona: a warm, theatrical wizard mentor. He treats tasks as quests and wins as victories,
which keeps a boring to-do list genuinely fun to come back to.

### Which organs it uses

- **Voice (Week 1).** The `persona_call.py` idea — a strong system prompt that never breaks
  character. Aldric's mentor voice is the whole reason the goal-tracking feels like a game
  instead of a chore.
- **Hands (Weeks 2–3).** `search_the_web` (Playwright + DuckDuckGo). When a quest needs a
  real fact — "what's the deadline for X", "docs for library Y" — he fetches it live instead
  of guessing.
- **Brain (Week 3).** The ReAct loop from `chat_agent.py`: reason → call a tool → read the
  result → act again. This is what lets "I finished the second one" turn into `list_goals()`
  → find #2 → `complete_goal(2)` → celebrate, all in one turn.
- **Self (Week 4).** `memory.json` for who I am, `goals.json` for what I'm doing. This is the
  organ that turns a chatbot into something that shows up *for* me.

### The new organ I still need
A **time / reminder sense**. I already added `current_time()` this week. The next step is
letting Aldric attach due-dates to quests and proactively surface "this is due tomorrow and
still open" — moving him from *reactive* (answers when asked) to *proactive* (checks in on
his own). That, plus the retrieval-based memory noted above, is the gap between this week's
demo and a final project I'd actually run every day.
