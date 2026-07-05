"""Step 5.1 — Fleet Ops Manager: reviews T2 proposals. Approve / reject / bump to T3.
Reads proposals+context, writes verdicts only. T3 is never touched — humans own it."""
import json

from src.db import get_client
from src.llm import ask_llm

PROMPT = """You are a fleet operations manager reviewing a recovery proposal
made by a junior planner. Be strict: approve only if the action is proportionate.

Exception: {exc_type} — {detail}
Customer tier: {tier} | Order priority: {priority} (1=highest)
Proposed action: {action}
Planner's reasoning: {reasoning}

Options:
- "approve": action is proportionate, execute it
- "reject": action is wrong or unnecessary (say why in one sentence)
- "bump": too risky even for you — a human dispatcher must decide

Reply ONLY JSON: {{"verdict": "approve"|"reject"|"bump", "reason": "one sentence"}}"""


def review():
    sb = get_client()
    t2 = (sb.table("proposals")
          .select("*, exceptions(type, detail, order_id)")
          .eq("status", "pending").eq("risk_tier", 2).execute().data)
    print(f"{len(t2)} T2 proposals to review.")

    for p in t2:
        exc = p["exceptions"]
        order = (sb.table("orders").select("customer_tier, priority")
                 .eq("id", exc["order_id"]).single().execute().data)
        raw = ask_llm(PROMPT.format(
            exc_type=exc["type"], detail=exc["detail"],
            tier=order["customer_tier"], priority=order["priority"],
            action=p["action"], reasoning=p["reasoning"]))
        try:
            v = json.loads(raw.replace("```json", "").replace("```", "").strip())
        except json.JSONDecodeError:
            print(f"  proposal {p['id']}: unusable answer — left pending")
            continue

        if v.get("verdict") == "approve":
            sb.table("proposals").update({"status": "approved"}).eq("id", p["id"]).execute()
            print(f"  ✔ approved {p['id']} ({p['action']}) — {v['reason']}")
        elif v.get("verdict") == "reject":
            sb.table("proposals").update({"status": "rejected"}).eq("id", p["id"]).execute()
            sb.table("exceptions").update({"status": "open"}) \
              .eq("id", p["exception_id"]).execute()   # back to Recovery for a rethink
            print(f"  ✘ rejected {p['id']} — {v['reason']}")
        elif v.get("verdict") == "bump":
            sb.table("proposals").update({"risk_tier": 3}).eq("id", p["id"]).execute()
            print(f"  ⬆ bumped {p['id']} to T3 (human) — {v['reason']}")


if __name__ == "__main__":
    review()