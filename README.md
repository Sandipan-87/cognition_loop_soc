# Cognition Loop: Building Autonomous ReAct Agents

Welcome to the Cognition Loop. This project bridges the gap between basic conversational chatbots and autonomous, action-driven AI systems.

## The Final Vision

Current consumer LLMs are passive systems: they require a user prompt, generate text, and halt. This project shifts that paradigm. Over the next eight weeks, you will engineer an active, autonomous agent capable of reasoning through multi-step problems and executing actions in the real world.

By the end of this project, you will build an orchestration engine capable of executing tasks such as:
> *"Query the internal documentation database to find the user's preferred music genre, then open a web browser, navigate to YouTube or Spotify, and autonomously search for and play a playlist matching that mood."*

To achieve this, the agent will independently:
1. Formulate a plan.
2. Utilize a Retrieval-Augmented Generation (RAG) tool to search internal documents.
3. Utilize browser automation tools to interact with live websites.
4. Process the observations and complete the objective without human intervention.

##  Week 1: Reading & Technical Resources

Before writing the control logic, it is critical to understand the underlying architecture of modern AI. Review these resources before starting the tasks.

### 1. Conceptual Foundations
* **The Mechanics of LLMs:** [[1hr Talk] Intro to Large Language Models by Andrej Karpathy](https://www.youtube.com/watch?v=zjkBMFhNj_g) — Demystifies how standard generative models are trained and why they hallucinate. Understand the training pipeline, tokenization, and the fundamental limitations of standard generative models.
* **The Shift to Agentic AI:** [Andrew Ng Explores The Rise Of AI Agents](https://www.youtube.com/watch?v=KrRD7r7y7NY) — Explains the conceptual shift from direct prompting to systems that utilize reflection, tool use, and planning.
* **The ReAct Framework:** [Prompt Engineering Guide: ReAct](https://www.promptingguide.ai/techniques/react) — Differentiate between standard prompting, Chain of Thought, and the ReAct methodology.
* **4Data Serialization (JSON & APIs)** - Understand why autonomous agents rely on strictly structured JSON data rather than conversational text to trigger external code.
### 2. Core API Documentation
* **Google GenAI SDK (Python):** [Official Documentation](https://ai.google.dev/api/python/google/genai) — Bookmark this. You will need it for understanding how to pass System Instructions, force JSON schemas, and handle rate limits.

## Week 2: Learning Resources

Read this before you start coding. It covers the ideas behind the three tasks so you understand what you are building. You do not need to finish every link so, pick what fills your gaps.

### A note on the model we use (please read)

In Week 1 you used **Gemini 2.5 Flash**. It works, but it burns through a lot of tokens quickly, so the free quota runs out fast and it can get slow or rate-limited during practice. From this week on, **do not use Gemini 2.5 Flash**. Use the **Groq API** instead — it is fast, has a generous free tier. All AI tasks below assume Groq.

### Groq API key setup

1. Go to https://console.groq.com/keys
2. Sign in and click **Create API Key**. Copy the key (you only see it once).
3. In the project root, open the `.env` file and add this line:
   ```
   GROQ_API_KEY=paste-your-key-here
   ```
4. In your code, load it like this (never hardcode the key):
   ```python
   import os
   from dotenv import load_dotenv
   from groq import Groq

   load_dotenv()
   client = Groq(api_key=os.environ["GROQ_API_KEY"])
   ```

Do not share this key or push it to GitHub. Keep your API key in `.env`, never in your code. Make sure `.env` is written inside your `.gitignore` file.



- Groq docs (just for reference): https://console.groq.com/docs/overview

### Tool / function calling with Groq

An LLM can do more than chat: you can give it tools (real Python functions). The model decides when a tool is needed, your code runs it and sends the result back, and the model uses that result to write its final answer. This is exactly the flow you build in the first task.

- Groq tool use docs (read this first): https://console.groq.com/docs/tool-use
- Groq local tool calling — full code walkthrough (docs): https://console.groq.com/docs/tool-use/local-tool-calling
- Build an AI function agent with Groq in Python (video): https://www.youtube.com/watch?v=FZJf4yaiVts

### Browser automation with Playwright

Playwright lets your code open a real browser, visit pages, type, click, and read what is on screen. You use this to open a website and to search and play a video.

- Playwright for Python — getting started (docs): https://playwright.dev/python/docs/intro
- Locators: how to find elements on a page (docs): https://playwright.dev/python/docs/locators
- Playwright Python browser automation crash course (video): https://www.youtube.com/watch?v=cO997sPYZ9U

# Week 3 Learning 

Read this before you start coding. It covers the one new idea this week: the ReAct loop. You do not need every link — pick what fills your gaps.

## What you should already know

- Week 2, `basic_tool.py`: a Groq agent that calls one tool, gets the result back as a `"role": "tool"` message, then answers. It does this for exactly one round.
- Week 2, `browser_test.py`: opening a page with Playwright and reading elements with locators.

Week 3 joins these two. The tool the agent calls is now a Playwright function, and the single round becomes a real loop.

## The one new idea: ReAct (Reason + Act)

A plain LLM only knows its training data. It cannot tell you today's top story or the current price of anything. ReAct fixes this by letting the model alternate between thinking and using tools:

1. **Reason** — decide what is missing.
2. **Act** — call a tool to get it.
3. **Observe** — read the tool's result.
4. **Repeat** — reason again; act again if needed.
5. **Answer** — reply once it has enough.

The model decides when to act. You supply the tools.

```
User:        What's the top story on Hacker News right now?
Thought:     No live data. Search the web.
Action:      search_the_web("top story Hacker News")
Observation: "Show HN: I built a database in Rust — 482 points..."
Thought:     Got it. Answer.
Answer:      The top story is "Show HN: I built a database in Rust" (482 points).
```

## The loop in code (the upgrade from Week 2)

An LLM call is stateless. The only memory is the `messages` list you resend every call. Each turn it grows: `user` -> `assistant` (a tool call) -> `tool` (your result) -> `assistant` (text).

In `basic_tool.py` you ran the tool **once**, then made a second call for the final answer. That is a ReAct loop with the loop removed. This week you put the loop back:

```python
while True:
    response = client.chat.completions.create(model=MODEL, messages=messages, tools=tools)
    msg = response.choices[0].message
    messages.append(msg)

    if not msg.tool_calls:        # plain text -> done
        print(msg.content)
        break

    for call in msg.tool_calls:   # model wants to act
        result = available_tools[call.function.name](**json.loads(call.function.arguments))
        messages.append({
            "role": "tool",
            "tool_call_id": call.id,
            "name": call.function.name,
            "content": json.dumps(result),
        })
    # loop again — the model now sees the result and can act again
```

That is the whole brain. The model can now search, read what came back, and search again before answering — something the single round in Week 2 could not do.

## Resources 

You already have the Groq tool-use docs and Playwright docs from Week 2 — reuse them. These are the new ones for the concept:


- ReAct project page, with diagrams: https://react-lm.github.io/
- Anthropic, "Building Effective Agents" (framework-free, very readable): https://www.anthropic.com/research/building-effective-agents
- Lilian Weng, "LLM Powered Autonomous Agents": https://lilianweng.github.io/posts/2023-06-23-agent/ (Just skim through this or use AI for summary)

Keeping this week's resources a bit lite , Let's majorly focus on the coding tasks.
We build the loop from scratch — no LangChain, no LlamaIndex. It is about 30 lines, and every framework is just a wrapper around it.

Setup is the same as Week 2 (same `.env`, same Groq key, same model). Now go to `WEEK3_TASKS.md`.

# Week 4 Learning Resources 

 There is one genuinely new technical idea — saving data to a file — one idea worth a deeper second look now that you have built a real agent, and a short stack of "lean back and watch/read" links to get you dreaming about your final project. Pick what fills your gaps; you do not need every link.

## What you should already know



- Week 1: talking to an LLM, giving it a persona with a system prompt (`persona_call.py`), and getting clean JSON back (`json_extractor.py`).
- Week 3: the ReAct loop, an in-chat `messages` list as memory, and chaining tools.

This week takes the persona from Week 1, the loop from Week 3, and adds the one thing neither had: memory that survives the program closing — plus structured state your agent can act on.

## The one new idea: persistence

Everything your agent has remembered so far lives in the `messages` list. That list is in RAM. The moment your program exits, it is gone — the agent has amnesia every time you press run.

Persistence means writing what matters to disk so it is still there next time. You do not need a database. A single JSON file your agent reads when it starts and writes when it learns something new is enough, and it is the same `json` you have used since Week 1.

```python
import json

# write
with open("memory.json", "w") as f:
    json.dump(["likes Python", "name is Sam"], f, indent=2)

# read
with open("memory.json") as f:
    facts = json.load(f)   # back to a Python list
```

That is the entire new concept. The context window is short-term memory; a file is long-term memory. Real assistants are built on exactly this split.

Links:

- Python `json` module (read `dump` and `load`): https://docs.python.org/3/library/json.html
- Reading and writing files in Python (clear walkthrough): https://realpython.com/read-write-files-python/
- Working with JSON in Python (short video): https://www.youtube.com/watch?v=9N6a-VLBa2I

## Going one step further: structured state

In File 2 your memory is a flat list of strings. In File 4 (the quest log) each item becomes a small object — `{"goal": "...", "done": false}`. That tiny change is a big idea: real agents do not store loose facts, they store **state with shape** they can update and reason over. A goal can be marked done; a fact usually cannot. Notice how naturally the same `json.load` / `json.dump` handles a list of dicts — you already know how to do this.

- Python dictionaries (quick refresher): https://realpython.com/python-dicts/
- Why JSON is the lingua franca of tools and APIs (short read): https://www.json.org/json-en.html

## Worth a second look: what makes an agent an agent

You have now built one. Re-read this with that experience — it lands completely differently than it would have in Week 2, and it is the best map for deciding what your final project should be.

- Anthropic, "Building Effective Agents": https://www.anthropic.com/research/building-effective-agents

As you read, notice that your Week 3 loop already *is* the core pattern they describe. You did not use a framework; you built the thing the frameworks wrap.

## For your final project: memory, goals, and reflection

These are the ideas the pros use to make an agent feel like it has a mind that persists. You do not need to implement them fully — skim them for inspiration and steal one idea for your `JOURNEY.md`.

- Lilian Weng, "LLM Powered Autonomous Agents" — the **memory** and **planning** sections map directly onto Files 2 and 4: https://lilianweng.github.io/posts/2023-06-23-agent/
- MemGPT / Letta — what happens when memory is too big for the context window (the exact problem the File 2 note warns about), solved properly: https://arxiv.org/abs/2310.08560
- Reflexion — agents that look back at what they did and write themselves a note to do better next time. A fun, achievable stretch: have your agent decide *on its own* what is worth `remember()`-ing at the end of a chat: https://arxiv.org/abs/2303.11366

## Worth a second look: personas and tool descriptions

Two small skills you will lean on for the rest of the project.

- A persona is just a well-written system prompt. The clearer and more specific it is, the more consistent the character. Anthropic's guide on system prompts: https://docs.anthropic.com/en/docs/build-with-claude/prompt-engineering/system-prompts
- The model decides when to use a tool based entirely on the tool's `description`. A vague description means the tool never gets called, or gets called wrongly. Treat tool descriptions as instructions to the model, not comments for yourself. (You already have the Groq tool-use docs from Week 2 — reuse them.)

## Good habits, again

- Print what you read from the file so you can *see* the memory and the quest log loading.
- Start any JSON file as a valid empty list `[]`, never a blank file.
- Keep your API key in `.env`, never in your code.

That is everything. Now open `TASKS_WEEK4.md`, give your agent a self that lasts.








