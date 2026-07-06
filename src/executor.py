"""Step 4.5 — the tier gate: auto-execute proposals.
Deterministic code only. No LLM anywhere in this file — by design."""
from datetime import datetime, timedelta

from src.db import get_client

AUTO_TIERS = (0, 1, 2, 3)   # everything auto-executes now


def execute_notify_delay(sb, order_id: int):
    sb.table("notifications").insert(
        {"order_id": order_id, "kind": "delay"}).execute()
    return "delay notification queued"


def execute_reschedule(sb, order_id: int):
    order = (sb.table("orders").select("window_start, window_end, customer_tier")
             .eq("id", order_id).single().execute().data)
    new_start = datetime.fromisoformat(order["window_start"]) + timedelta(days=1)
    new_end = datetime.fromisoformat(order["window_end"]) + timedelta(days=1)

    update = {
        "status": "new",                      # planner will pick it up again
        "window_start": new_start.isoformat(),
        "window_end": new_end.isoformat(),
    }
    if order["customer_tier"] == "enterprise":
        update["priority"] = 1   # special care: jump the queue tomorrow

    sb.table("orders").update(update).eq("id", order_id).execute()
    sb.table("notifications").insert(
        {"order_id": order_id, "kind": "reschedule"}).execute()
    return "order moved to tomorrow, back in planning pool, customer queued"


ACTIONS = {
    "notify_delay": execute_notify_delay,
    "reschedule_next_day": execute_reschedule,
}


def run():
    sb = get_client()
    rows = (sb.table("proposals")
            .select("*, exceptions(order_id)")
            .in_("status", ["pending", "approved"]).execute().data)
    auto = [p for p in rows if p["action"] in ACTIONS]
    frozen = [p for p in rows if p not in auto]

    for p in auto:
        order_id = p["exceptions"]["order_id"]
        result = ACTIONS[p["action"]](sb, order_id)
        sb.table("proposals").update({"status": "executed"}).eq("id", p["id"]).execute()
        sb.table("exceptions").update({"status": "resolved"}) \
          .eq("id", p["exception_id"]).execute()
        print(f"✅ T{p['risk_tier']} proposal {p['id']} ({p['action']}) "
              f"order #{order_id}: {result}")

    for p in frozen:
        print(f"⏸  T{p['risk_tier']} proposal {p['id']} ({p['action']}) — "
              f"no handler, left pending")
    print(f"\nExecuted {len(auto)}, frozen {len(frozen)}.")


if __name__ == "__main__":
    run()