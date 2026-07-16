# Autonomous MLOps Tuning Pipeline Orchestrator

An autonomous, state-driven Machine Learning engineering agent built around a persistent, transactional disk state architecture. The system decomposes high-level optimization requests into structured sub-tasks and executes them sequentially using a robust ReAct (Reasoning + Acting) execution engine.

---

## 🏗️ Architecture & Core Principles

* **State-Driven Orchestration (`plan.json`):** The entire execution matrix is managed on disk rather than volatile RAM. If the system is interrupted by a network timeout, rate limit, or user abort (`Ctrl+C`), it cleanly resumes from the exact point of failure without losing historical state.
* **API Hardening:** Equipped with an exponential backoff engine to dynamically mitigate HTTP 429 rate limit errors.
* **Bounded Context Memory Loop:** Bypasses context window bloat by feeding a rolling evaluation history to the LLM core, maintaining performance discipline.
* **Cognitive Organs Framework:**
  * **Voice:** Strict `MATRIX` persona acting as a terse Senior ML Engineer who evaluates metadata systematically.
  * **Hands:** Headless web-browser context layer powered by Playwright for live documentation mining.
  * **Brain:** Dynamic inner loop driving functional execution via structured function calling.
  * **Self:** Decoupled persistence layer rendering the active runtime process safely disposable.

---

## 🛠️ System Tools & Capabilities

The orchestrator dynamically chooses and maps data from three customized engineering interfaces:
1. `read_local_dataset_metadata`: Extracts target shapes, target profiles, and historical baseline scores.
2. `search_the_web`: Heads up headless browser crawls via DuckDuckGo to extract tuning methodologies.
3. `open_page`: Downloads raw technical markdown text profiles from direct API documentation structures.

---

## 🚀 Getting Started

### 1. Prerequisites
Ensure you have the core packages installed in your virtual environment:
```bash
pip install playwright python-dotenv groq
playwright install chromium


2. Configuration
Create a secure .env file in the project directory:

Code snippet
GROQ_API_KEY=your_actual_api_key_here


3. Execution
Launch the pipeline state engine:

Bash
python capstone.py

Production Convergence Trace Log:
Current working directory: D:\IITB PLACEMENTS\SOC
Looking for: d:\IITB PLACEMENTS\SOC\mentee_submissions\Sneha_Sonkar\capstone\plan.json

[MATRIX CORE]: Constructing optimization matrices...
[MATRIX CORE]: Plan logged cleanly — 5 parameters active:
  [1] Inspect dataset metadata
  [2] Diagnose current model performance
  [3] Gather only relevant information from official documentation
  [4] Recommend concrete hyperparameter changes
  [5] Produce a final optimization report

📉 [MATRIX PIPELINE WORKER] Running Step 1/5: 👉 Inspect dataset metadata
  📊 [MATRIX REACT ROUTER] Calling: read_local_dataset_metadata({'file_path': 'dataset_metadata.json'})
  ✅ Tool 'read_local_dataset_metadata' completed.

📄 RESULT OF STEP 1 & 2 (Metadata & Performance Diagnosis)
----------------------------------------------------------------------
Current baseline: XGBoost (ROC-AUC: 0.81, Accuracy: 0.74, Loss Var: 0.08)
Issues detected: Class balance near optimal (~50.4% positive / 49.6% negative) 
                 -> Oversampling/undersampling explicitly bypassed.
Recommended changes: Dataset size (70,000 records > 50,000) 
                 -> Mandating Optuna/Bayesian Optimization over GridSearch.

📉 [MATRIX PIPELINE WORKER] Running Step 3/5: 👉 Gather relevant information
  🌐 [Tool] Scanning external web nodes for: 'XGBoost hyperparameter tuning'...
  📖 Opening [https://xgboost.readthedocs.io/en/latest/parameter.html](https://xgboost.readthedocs.io/en/latest/parameter.html)
  ✅ Tool completed.

📉 [MATRIX PIPELINE WORKER] Running Step 4 & 5: 👉 Final Convergence
======================================================================
📄 FINAL OPTIMIZATION REPORT (Step 5/5)
======================================================================
Recommended Training Changes:
1. XGBoost: Maximize interaction bounds via max_depth: 6, learning_rate: 0.1, gamma: 0.1
2. LightGBM: Maximize leaves via num_leaves: 31, max_depth: -1, learning_rate: 0.1
3. CatBoost: Regularize variance via depth: 6, learning_rate: 0.1, iterations: 1000

Expected Improvement: Expected model generalization bound lifting to ~0.85+ ROC-AUC.
======================================================================
📈 [MATRIX CORE]: Master convergence achieved. Verification logs complete.