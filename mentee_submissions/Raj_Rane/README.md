# Capstone Project: The Planner Agent

The Planner Agent is an autonomous, state-driven orchestration agent. It takes a high-level goal from the user, decomposes it into an ordered list of tasks, writes the state to a local `plan.json` file, and executes the tasks one by one. 

The core feature of this agent is **resumability**: all memory of what to do and what is done lives on disk in `plan.json`. If you stop the execution mid-run (e.g. Ctrl-C, crash, or rate limit) and restart the program, the agent picks up exactly from the last unfinished step.

---

## The Four Organs of the Agent

1. **Voice**: Reginald, a highly formal and direct 19th-century butler project manager. Enforced strictly using system instructions.
2. **Hands**: Interacts with the real world using custom Python functions:
   - `search_the_web(query)`: Uses a fallback requests/Playwright scraper to fetch DuckDuckGo search results.
   - `write_file(filename, content)`: Writes generated files/reports to local disk.
   - `read_file(filename)`: Reads local file data.
3. **Brain**: A ReAct reasoning loop (Reason -> Act -> Observe) executing inside each step when tools are needed. It features a custom **self-healing parser** that intercepts Groq's XML-tag tool-calling exceptions (BadRequestError) and manually executes the tool parameters.
4. **Self**: Orchestrated state machine (`plan.json`) that saves state atomically to disk after every single step.

---

## Requirements & Setup

1. Make sure your python virtual environment is activated.
2. Ensure you have the Groq SDK installed:
   ```bash
   pip install groq python-dotenv requests playwright
   ```
3. Set your Groq API key in the `.env` file in the root folder:
   ```env
   GROQ_API_KEY=your_actual_key_here
   ```

---

## How to Run

Run the script from your terminal:
```bash
python capstone.py
```

### Initial Run
On the first run, the agent will prompt you for an overall goal. It will decompose this goal into a series of steps, write them to `plan.json`, and begin execution.

### Resuming Run
If the agent is killed mid-run, simply execute the same command again:
```bash
python capstone.py
```
It will automatically detect the existing `plan.json` and resume execution from the first unfinished task.

---

## Example Run Walkthrough

### 1. Goal Input
```
🤖 Welcome to the Planner Agent!
👉 Enter your overall goal: Research the current market price of Solana and write a summary to solana_price.txt
```

### 2. Plan Generation (`plan.json` initialization)
```
📝 Decomposing goal: 'Research the current market price of Solana and write a summary to solana_price.txt'
📋 Generated 3 steps:
  1. Search for the current price of Solana (SOL) in USD
  2. Format a summary report with the retrieved Solana price details
  3. Write the formatted summary report to solana_price.txt
💾 Plan saved to plan.json. Starting execution...
```

### 3. Step 1 Execution (Web Search)
```
🚀 Working on Step 1/3: Search for the current price of Solana (SOL) in USD
    [Brain] Iteration 1/5
    🔧 Tool: search_the_web({'query': 'current Solana price USD'})
  🔍 Searching web for: 'current Solana price USD'
    📄 Got 758 chars of results
    [Brain] Iteration 2/5
    🤖 Final Step Output: According to the latest market data, the current price of Solana (SOL) is approximately $138.45 USD, with a 24-hour trading range of...
✅ Completed Step 1! State flushed to plan.json.
============================================================
```

### 4. Restarting mid-run (Simulating crash after Step 1 completes)
If you stop the process here and run it again:
```
🔄 Resuming plan from plan.json!
🎯 Overall Goal: Research the current market price of Solana and write a summary to solana_price.txt
📈 Resuming at Step 2/3
📝 Next Task: Format a summary report with the retrieved Solana price details
------------------------------------------------------------

🚀 Working on Step 2/3: Format a summary report with the retrieved Solana price details
    [Brain] Iteration 1/5
    🤖 Final Step Output: Report:
Solana (SOL) Market Summary
Price: $138.45 USD
Status: Verified...
✅ Completed Step 2! State flushed to plan.json.
============================================================
```

### 5. Final Step Completion (File Writing)
```
🚀 Working on Step 3/3: Write the formatted summary report to solana_price.txt
    [Brain] Iteration 1/5
    🔧 Tool: write_file({'filename': 'solana_price.txt', 'content': '...' })
    📄 Got 39 chars of results
    [Brain] Iteration 2/5
    🤖 Final Step Output: The report has been written successfully to solana_price.txt.
✅ Completed Step 3! State flushed to plan.json.
============================================================

🎉 All tasks completed!
```
