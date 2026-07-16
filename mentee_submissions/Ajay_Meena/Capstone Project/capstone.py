from planner import load_plan, make_plan, run_loop
from tools import recall, list_goals

PERSONA = """You are an autonomous planning agent — precise, efficient, no fluff.
You break goals into steps and execute them one at a time.
When a step needs real information, you use search_the_web.
When you learn something worth keeping, you call remember.
You never skip steps. You never make up facts. You report results clearly."""


def main():
    print("="*50)
    print("  Planner Agent")
    print("="*50)

    memory = recall()
    goals = list_goals()

    if memory != "Nothing stored yet.":
        print(f"\n[Memory loaded]\n{memory}")
    if goals != "No goals yet.":
        print(f"\n[Quest log]\n{goals}")

    plan = load_plan()

    if plan and plan.get("status") == "in_progress":
        done = [s for s in plan["steps"] if s["status"] == "done"]
        total = len(plan["steps"])
        print(f"\n[Resuming plan: {plan['goal']}]")
        print(f"[Progress: {len(done)}/{total} steps done]\n")
        run_loop(plan, PERSONA)

    elif plan and plan.get("status") == "done":
        print(f"\n[Last plan '{plan['goal']}' is already complete.]")
        choice = input("Start a new plan? (y/n): ").strip().lower()
        if choice != "y":
            return
        goal = input("\nEnter your goal: ").strip()
        if not goal:
            print("No goal entered.")
            return
        plan = make_plan(goal)
        run_loop(plan, PERSONA)

    else:
        goal = input("\nEnter your goal: ").strip()
        if not goal:
            print("No goal entered.")
            return
        plan = make_plan(goal)
        run_loop(plan, PERSONA)


if __name__ == "__main__":
    main()