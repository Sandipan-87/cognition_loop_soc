# Cognition Loop: Journey Log & Capstone Proposal
**Mentee:** Saket Vispute  
**Path:** `mentee_submissions/Saket_Vispute/JOURNEY.md`

---

## 📅 Retrospective: Weeks 1 – 3

### Week 1: Infrastructure and Control
* **Key Achievements:** Explored the Google Gemini API with `google-genai` client libraries, designed robust rate-limit retry handlers with backoff mechanics, and established structured output configurations (`response_mime_type="application/json"`).
* **Lessons Learned:** Handing raw text from LLMs is unreliable for automation. Forcing JSON outputs with deterministic temperatures (`0.0`) is the cornerstone of building downstream APIs and integrations.

### Week 2: Web Automation & Basic Tool Use
* **Key Achievements:** Wired Python functions to the Groq API, scraping news from Hacker News, and driving visual/headless Chromium via Playwright to automate YouTube video playback and bypass advertisements.
* **Lessons Learned:** Web sites change layouts, throw CAPTCHAs, and have bloated networks. Implementing timeouts, robust CSS locators, and headless-fallback strategies is mandatory for resilient browser automation.

### Week 3: Autonomous Agents (ReAct Loop)
* **Key Achievements:** Implemented the full ReAct (Reasoning and Acting) loop from scratch using standard Groq chat completions, tool call mapping, and a persistent `messages` conversation history list.
* **Lessons Learned:** The ReAct loop is simple yet incredibly powerful. Passing structured tool logs (`{"role": "tool", "content": "..."}`) directly back to the LLM allows it to correct course and gather information incrementally.

---

## 🔮 Capstone Project Seed: The Market Research Planner Agent

### The One-Liner
> **My final project is a "Market Research Planner Agent" named Alpha that decomposes and executes comprehensive company research and competitive analysis reports for investors and equity analysts.**

### Voice (Persona)
* **Name:** Alpha
* **Character:** A veteran equity research analyst and senior market strategist.
* **Tone:** Terse, objective, highly analytical, and quantitative. Communicates in structured markdown lists, bullet points, and tables. Avoids chatty filler text.

### Organs and Tools Integration

#### 1. Voice (System Instructions)
Runs a customized, strict prompt instructing the model to analyze company news, stock performance, and competitor layouts objectively and format everything in markdown report templates.

#### 2. Hands (Tools)
The agent integrates the following core tools:
* `search_the_web(query)`: Scrapes DuckDuckGo search results.
* `open_page(url)`: Scrapes text content (first 3000 chars) from financial articles and investor relations sites.
* `get_stock_price(ticker)`: Fetches real-time price, exchange details, and currency from Yahoo Finance.
* `write_report_file(filename, content)`: Saves the compiled research dossier as a local file.

#### 3. Brain (Orchestrated Loop)
* The agent takes one large research objective: *"Produce a complete market research report for NVIDIA (NVDA)."*
* It calls `make_plan` to generate a structured 4-5 step research roadmap and writes it into `plan.json`.
* The main orchestrator loops through each step, utilizing internal ReAct reasoning and browser/API tools to execute it.
* Results of each step are stored on disk instantly.

#### 4. Self (State Persistence & Resumability)
* Backed by `plan.json` on disk.
* The agent reads the current execution pointer and step states upon launch.
* If the script crashes or is terminated using `Ctrl-C` during step 3, running the script again immediately resumes from step 3 without re-running steps 1 and 2, saving substantial token cost.
