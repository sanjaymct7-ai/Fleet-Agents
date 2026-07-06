"""Step 4.2 — Live Tracking agent: polls reality, raises exceptions.
Runs ALONGSIDE the simulator in a second terminal. Read stops -> write exceptions."""
import time

from src.db import get_client

LATE_THRESHOLD_MIN = 15   # more than this behind plan = an exception
POLL_SECONDS = 2


def minutes(ts: str) -> int:
    return int(ts[11:13]) * 60 + int(ts[14:16])


def raise_exception(sb, exc_type, order_id, route_id, detail):
    try:
        sb.table("exceptions").insert({
            "type": exc_type, "order_id": order_id,
            "route_id": route_id, "detail": detail,
        }).execute()
        print(f"🚨 RAISED {exc_type}: order #{order_id} — {detail}")
    except Exception:
        pass  # unique constraint said "already raised" — exactly what we want


def scan(sb) -> int:
    done = (sb.table("route_stops")
            .select("route_id, order_id, planned_arrival, actual_arrival, status")
            .in_("status", ["done", "failed"])
            .not_.is_("actual_arrival", "null").execute().data)
    for s in done:
        if s["status"] == "failed":
            raise_exception(sb, "failed_delivery", s["order_id"], s["route_id"],
                            "delivery failed (nobody home / wrong address)")
        else:
            gap = minutes(s["actual_arrival"]) - minutes(s["planned_arrival"])
            if gap > LATE_THRESHOLD_MIN:
                raise_exception(sb, "late", s["order_id"], s["route_id"],
                                f"arrived {gap} min after plan")
    return len(done)


def watch():
    sb = get_client()
    total = (sb.table("route_stops").select("id", count="exact", head=True)
             .execute().count)
    print(f"👁  Tracking {total} stops... (Ctrl+C to stop)")
    while True:
        completed = scan(sb)
        if completed >= total:
            print("All stops accounted for. Watch ends.")
            break
        time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    watch()