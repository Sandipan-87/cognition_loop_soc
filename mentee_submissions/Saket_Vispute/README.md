# Cognition Loop Coursework & Capstone Submission - Saket Vispute

This directory contains the implementations for the Cognition Loop autonomous ReAct agents coursework and the final Capstone project.

## 📂 Project Structure
```
mentee_submissions/Saket_Vispute/
├── README.md               <-- Coursework and Capstone docs (this file)
├── JOURNEY.md              <-- Retrospective and Capstone proposal
├── plan.json               <-- Orchestrator plan state file (loaded/saved dynamically)
├── capstone.py             <-- Final Capstone: State-Driven Planner Agent
├── Week1/
│   ├── basic_call.py
│   ├── rate_limit_handler.py
│   ├── persona_call.py
│   └── json_extractor.py
├── Week2/
│   ├── basic_tool.py
│   ├── browser_test.py
│   └── youtube_autoplay.py
├── Week3/
│   ├── research_agent.py
│   └── chat_agent.py
└── Week4/
    ├── my_assistant.py     <-- Week 4: Persistent Market Analyst Agent
    ├── memory.json         <-- Persistent memory database
    └── goals.json          <-- Persistent quest/goals tracker
```

---

## 🚀 Final Capstone Project: State-Driven Market Research Planner Agent

The final capstone integrates all agentic design patterns into a resilient **State Machine Orchestrator** on disk:

* **Disk-Based Memory (`plan.json`):** Instead of storing progress in ephemeral process memory, the agent writes its plan, execution statuses (`pending`, `in_progress`, `done`), and gathered results to disk. 
* **State Resumability:** If you run `python capstone.py`, hand it a goal, watch it start compiling research, and terminate it using `Ctrl-C` mid-way through step 2, running the script again loads the saved plan from disk and resumes execution from step 2 without re-running completed steps.
* **Completions Hardening:** Automatically recovers from API rate limiting (HTTP 429) using exponential backoff retry cycles.
* **Token Budget (TPM) Optimization:** Employs minimal, trimmed contexts (under 1000 tokens) to ensure it stays well within free-tier limits even on complex, multi-step plans.
* **Integrated Skills:**
  * DuckDuckGo browser-based search engine scraper.
  * Deep webpage scrapper (extracts text and limits context window sizes).
  * Real-time stock symbol ticker data parser from Yahoo Finance.
  * Local file writer.

### Running the Capstone
1. Launch the script:
   ```bash
   python mentee_submissions/Saket_Vispute/capstone.py
   ```
2. Enter a research target when prompted (e.g., `Analyze Nvidia (NVDA) market status`).
3. The planner will generate 4 sequential tasks in `plan.json` and start executing them in order.
4. **Resumability Test:** Press `Ctrl-C` during step 2 or 3. Run the script again. It will greet you, load your existing plan, and resume from the interrupted step.

---

## 🗓️ Week 4: Persistent Market Analyst Agent

Week 4 focuses on giving the agent a **self**—persistent long-term memory and structured goals.

*   **[my_assistant.py](file:///mnt/c/Users/Saket/Desktop/Projects/Cognition-Loop/cognition_loop_soc/mentee_submissions/Saket_Vispute/Week4/my_assistant.py)**: An interactive chat assistant configured with a professional Market Analyst persona named *Alpha*.
*   **Persistent Memory (`memory.json`)**: Employs `remember()` and `recall()` tools to record preferences and recall facts about the Client across CLI restarts.
*   **Persistent Goals (`goals.json`)**: Implements `add_goal()`, `list_goals()`, and `complete_goal()` to coordinate research targets over days.
*   **Stock Price Lookups**: Integrates `get_stock_price()` to fetch current stock valuations and exchange metrics keylessly from Yahoo Finance.

### Running Week 4 Agent
```bash
python mentee_submissions/Saket_Vispute/Week4/my_assistant.py
```

---

## 🗓️ Week 3: Autonomous Agents (ReAct Loop)
*   **[research_agent.py](file:///mnt/c/Users/Saket/Desktop/Projects/Cognition-Loop/cognition_loop_soc/mentee_submissions/Saket_Vispute/Week3/research_agent.py)**: Single-query autonomous ReAct search agent.
*   **[chat_agent.py](file:///mnt/c/Users/Saket/Desktop/Projects/Cognition-Loop/cognition_loop_soc/mentee_submissions/Saket_Vispute/Week3/chat_agent.py)**: Interactive multi-turn assistant with memory and web tools chaining.

---

## 🗓️ Week 2: Web Automation & Basic Tool Use
*   **[basic_tool.py](file:///mnt/c/Users/Saket/Desktop/Projects/Cognition-Loop/cognition_loop_soc/mentee_submissions/Saket_Vispute/Week2/basic_tool.py)**: Weather geocoding lookups using Groq tool calling.
*   **[browser_test.py](file:///mnt/c/Users/Saket/Desktop/Projects/Cognition-Loop/cognition_loop_soc/mentee_submissions/Saket_Vispute/Week2/browser_test.py)**: Scrapes Hacker News headlines.
*   **[youtube_autoplay.py](file:///mnt/c/Users/Saket/Desktop/Projects/Cognition-Loop/cognition_loop_soc/mentee_submissions/Saket_Vispute/Week2/youtube_autoplay.py)**: Playwright script to search and play YouTube videos with ad-bypassing.

---

## 🗓️ Week 1: Infrastructure and Control
*   **[basic_call.py](file:///mnt/c/Users/Saket/Desktop/Projects/Cognition-Loop/cognition_loop_soc/mentee_submissions/Saket_Vispute/Week1/basic_call.py)**: Basic Gemini API connection.
*   **[rate_limit_handler.py](file:///mnt/c/Users/Saket/Desktop/Projects/Cognition-Loop/cognition_loop_soc/mentee_submissions/Saket_Vispute/Week1/rate_limit_handler.py)**: Sleep-backoff retry handler for rate limits.
*   **[persona_call.py](file:///mnt/c/Users/Saket/Desktop/Projects/Cognition-Loop/cognition_loop_soc/mentee_submissions/Saket_Vispute/Week1/persona_call.py)**: Specific persona configuration using system instructions.
*   **[json_extractor.py](file:///mnt/c/Users/Saket/Desktop/Projects/Cognition-Loop/cognition_loop_soc/mentee_submissions/Saket_Vispute/Week1/json_extractor.py)**: Strictly formatted JSON extraction with Gemini.

---

## ⚙️ Environment Setup & Installation

Ensure all required dependencies are installed:
```bash
pip install google-genai groq python-dotenv requests playwright
playwright install chromium
```

Verify your API keys are configured in your local `.env` in the root of the project:
```env
GEMINI_API_KEY=your_gemini_api_key
GROQ_API_KEY=your_groq_api_key
```
