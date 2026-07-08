"""Recovery agent (5/8): judge exceptions, PROPOSE fixes. Never executes.
Reads exceptions+orders, writes proposals only.
LLM chooses from a fixed menu; deterministic rules assign risk tiers.
Everything auto-executes — no human approval required."""
import json

from src.db import get_client
from src.llm import ask_llm

MENU = ["notify_delay", "reschedule_next_day"]

PROMPT = """You are a logistics recovery planner. An exception occurred.
Exception: {exc_type} — {detail}
Order: #{order_id}, customer tier: {tier}

Choose ONE action from exactly this list: {menu}
Guidance: minor lateness needs only a delay notification; a failed
delivery needs rescheduling.

Reply with ONLY JSON: {{"action": "...", "reasoning": "one sentence"}}"""


def risk_tier(action: str, tier: str, exc_type: str) -> int:
    """Deterministic rules decide risk — never the LLM.
    Everything auto-executes; tiers just control visibility/flagging
    in the feed and daily report, not human approval."""
    if exc_type == "failed_delivery":
        return 1
    if tier == "enterprise":
        return 1
    return 0


def judge(exc: dict, order: dict) -> dict | None:
    raw = ask_llm(PROMPT.format(
        exc_type=exc["type"], detail=exc["detail"], order_id=order["id"],
        tier=order["customer_tier"], menu=MENU))
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

        # Route-level exception (no_driver): no order, no customer action
        # possible — just log it and resolve, nothing to approve or execute.
        if exc["order_id"] is None:
            sb.table("exceptions").update({"status": "resolved"}).eq("id", exc["id"]).execute()
            print(f"  exception {exc['id']} (no_driver) -> logged, resolved "
                  f"(staffing note — no customer action available)")
            continue

        order = (sb.table("orders").select("id, customer_tier")
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