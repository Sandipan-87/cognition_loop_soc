import io
import contextlib
import streamlit as st

from planner import load_plan, save_plan, make_plan, execute_step
from tools import recall, list_goals
from capstone import PERSONA

st.set_page_config(page_title="Planner Agent", layout="wide")

if "plan" not in st.session_state:
    st.session_state.plan = load_plan()
if "log" not in st.session_state:
    st.session_state.log = ""
if "auto_run" not in st.session_state:
    st.session_state.auto_run = False


def run_captured(fn, *args, **kwargs):
    """Run a planner function, capturing its print() output into the Agent Log."""
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        result = fn(*args, **kwargs)
    st.session_state.log += buf.getvalue()
    return result


st.title("🧭 Planner Agent")

# ---------- Sidebar ----------
with st.sidebar:
    st.header("Goal")
    goal_input = st.text_input("Enter a new goal")
    
    # Updated to width="stretch" to fix Streamlit warning
    if st.button("Start Plan", width="stretch"):
        if goal_input.strip():
            # Stop any existing auto-runs
            st.session_state.auto_run = False 
            plan = run_captured(make_plan, goal_input.strip())
            st.session_state.plan = plan
            st.rerun()
        else:
            st.warning("Enter a goal first.")

    st.divider()
    st.header("Memory")
    st.text(recall())

    st.header("Quest Log")
    st.text(list_goals())

plan = st.session_state.plan

col1, col2 = st.columns([2, 1])

# ---------- Plan Viewer ----------
with col1:
    st.subheader("Plan")
    if plan and plan.get("steps"):
        st.caption(f"Goal: {plan['goal']}  |  Status: {plan['status']}")
        rows = [
            {
                "Step": s["id"],
                "Task": s["task"],
                "Status": s["status"],
                "Result": s.get("result"),
            }
            for s in plan["steps"]
        ]
        # Updated to width="stretch"
        st.dataframe(rows, width="stretch", hide_index=True)
    else:
        st.info("No active plan. Enter a goal in the sidebar and click **Start Plan**.")

# ---------- Controls ----------
with col2:
    st.subheader("Controls")

    pending = [s for s in plan.get("steps", []) if s["status"] != "done"] if plan else []

    # Updated to width="stretch"
    if st.button("▶ Run Next Step", disabled=not pending, width="stretch"):
        st.session_state.auto_run = False
        step = pending[0]
        run_captured(execute_step, plan, step, PERSONA)
        st.session_state.plan = load_plan()
        st.rerun()

    # Updated to width="stretch"
    if st.button("⏭ Run All", disabled=not pending, width="stretch"):
        st.session_state.auto_run = True
        st.rerun()

    # Updated to width="stretch"
    if st.button("🗑 Clear Log", width="stretch"):
        st.session_state.log = ""
        st.rerun()

# ---------- Agent Log ----------
st.subheader("Agent Log")
st.text_area(
    "log",
    value=st.session_state.log,
    height=300,
    disabled=True,
    label_visibility="collapsed",
)

# ---------- Auto-Run Execution Hook ----------
# If Run All was clicked, we execute one step and then trigger a rerun.
# This prevents the UI from freezing and updates the screen live.
if st.session_state.auto_run and pending:
    step = pending[0]
    run_captured(execute_step, plan, step, PERSONA)
    st.session_state.plan = load_plan()
    
    if len(pending) > 1:
        st.rerun()
    else:
        st.session_state.auto_run = False
        st.rerun()