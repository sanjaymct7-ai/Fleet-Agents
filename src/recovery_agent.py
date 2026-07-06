"""Step 4.4 — Recovery agent: judge exceptions, PROPOSE fixes. Never executes.
Reads exceptions+orders, writes proposals only."""
import json

from src.db import get_client
from src.llm import ask_llm

MENU = ["notify_delay", "reschedule_next_day", "escalate_to_manager"]

PROMPT = """You are a logistics recovery planner. An exception occurred.
Exception: {exc_type} — {detail}
Order: #{order_id}, customer tier: {tier}, priority: {priority} (1=highest)

Choose ONE action from exactly this list: {menu}
Guidance: minor lateness usually needs only a delay notification; a failed
delivery usually needs rescheduling; anything involving an enterprise customer
or priority 1 deserves escalation.

Reply with ONLY JSON: {{"action": "...", "reasoning": "one sentence"}}"""


def risk_tier(action: str, tier: str, exc_type: str) -> int:
    """Deterministic rules decide risk — never the LLM."""
    if tier == "enterprise" or action == "escalate_to_manager":
        return 3
    if exc_type == "failed_delivery" or action == "reschedule_next_day":
        return 2 if tier == "premium" else 1
    return 0  # notify_delay for a standard customer


def judge(exc: dict, order: dict) -> dict | None:
    raw = ask_llm(PROMPT.format(
        exc_type=exc["type"], detail=exc["detail"], order_id=order["id"],
        tier=order["customer_tier"], priority=order["priority"], menu=MENU))
    try:
        data = json.loads(raw.replace("```json", "").replace("```", "").strip())
    except json.JSONDecodeError:
        return None
    if data.get("action") not in MENU:   # the gate, same as Intake's
        return None
    return data


def run():
    sb = get_client()
    open_excs = sb.table("exceptions").select("*").eq("status", "open").execute().data
    print(f"{len(open_excs)} open exceptions to judge.")
    for exc in open_excs:
        if exc["order_id"] is None:      # route-level exception (no_driver)
            sb.table("proposals").insert({
                "exception_id": exc["id"], "action": "escalate_to_manager",
                "reasoning": "entire route unassigned — needs staffing decision",
                "risk_tier": 3,
            }).execute()
            sb.table("exceptions").update({"status": "proposed"}).eq("id", exc["id"]).execute()
            print(f"  exception {exc['id']} (no_driver) -> escalate [T3]")
            continue
        order = (sb.table("orders").select("id, customer_tier, priority")
                 .eq("id", exc["order_id"]).single().execute().data)
        verdict = judge(exc, order)
        if verdict is None:
            print(f"  exception {exc['id']}: LLM answer unusable — left open for retry")
            continue
        tier = risk_tier(verdict["action"], order["customer_tier"], exc["type"])
        sb.table("proposals").insert({
            "exception_id": exc["id"], "action": verdict["action"],
            "reasoning": verdict["reasoning"], "risk_tier": tier,
        }).execute()
        sb.table("exceptions").update({"status": "proposed"}).eq("id", exc["id"]).execute()
        print(f"  exception {exc['id']} ({exc['type']}, {order['customer_tier']}) "
              f"-> {verdict['action']} [T{tier}] — {verdict['reasoning']}")


if __name__ == "__main__":
    run()