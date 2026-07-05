"""Step 3.3 — play out the day in accelerated time, injecting reality."""
import random
import time

from src.db import get_client

SPEED = 0.03          # real seconds per simulated minute (~30s for a full day)
random.seed()         # set a number here, e.g. random.seed(42), for repeatable days

# --- the reality model ---
P_TRAFFIC_PER_ROUTE = 0.30    # chance a route hits a traffic jam somewhere
TRAFFIC_DELAY = (15, 40)      # minutes added to every remaining stop
P_STOP_LATE = 0.20            # chance an individual stop slips
STOP_DELAY = (5, 25)
P_DELIVERY_FAILS = 0.05       # nobody home / wrong address


def hhmm(m):
    return f"{m // 60:02d}:{m % 60:02d}"


def load_day(sb):
    """Assigned routes -> list of stop-events sorted by planned time."""
    routes = (sb.table("routes").select("id, driver_id, drivers(name)")
              .eq("status", "assigned").execute().data)
    events = []
    for r in routes:
        stops = (sb.table("route_stops")
                 .select("id, order_id, seq, planned_arrival")
                 .eq("route_id", r["id"]).order("seq").execute().data)
        for s in stops:
            planned = int(s["planned_arrival"][11:13]) * 60 + int(s["planned_arrival"][14:16])
            events.append({"route_id": r["id"], "driver": r["drivers"]["name"],
                           "stop_id": s["id"], "order_id": s["order_id"],
                           "seq": s["seq"], "planned": planned,
                           "day": s["planned_arrival"][:10]})
    return sorted(events, key=lambda e: e["planned"])


def inject_reality(events):
    """Decide, per route and per stop, what ACTUALLY happens."""
    delays = {}  # route_id -> traffic delay applied from a random point on
    for rid in {e["route_id"] for e in events}:
        if random.random() < P_TRAFFIC_PER_ROUTE:
            route_ev = [e for e in events if e["route_id"] == rid]
            start_seq = random.choice(route_ev)["seq"]
            delays[rid] = (start_seq, random.randint(*TRAFFIC_DELAY))
    for e in events:
        delay = 0
        if e["route_id"] in delays:
            from_seq, minutes = delays[e["route_id"]]
            if e["seq"] >= from_seq:
                delay += minutes
                e["traffic"] = True
        if random.random() < P_STOP_LATE:
            delay += random.randint(*STOP_DELAY)
        e["actual"] = e["planned"] + delay
        e["failed"] = random.random() < P_DELIVERY_FAILS
    return sorted(events, key=lambda e: e["actual"])


def run():
    sb = get_client()
    events = inject_reality(load_day(sb))
    if not events:
        print("Nothing to simulate — dispatch some routes first.")
        return

    clock = events[0]["actual"]
    print(f"=== DAY BEGINS at {hhmm(clock)} — {len(events)} deliveries scheduled ===")
    for e in events:
        while clock < e["actual"]:
            clock += 1
            time.sleep(SPEED)
        gap = e["actual"] - e["planned"]
        if e["failed"]:
            status, order_status, tag = "failed", "failed", "❌ DELIVERY FAILED (nobody home)"
        else:
            status, order_status = "done", "delivered"
            tag = ("✅ on time" if gap <= 5 else
                   f"⚠️ LATE by {gap} min" + (" (traffic)" if e.get("traffic") else ""))
        sb.table("route_stops").update({
            "status": status,
            "actual_arrival": f"{e['day']}T{hhmm(e['actual'])}:00",
        }).eq("id", e["stop_id"]).execute()
        sb.table("orders").update({"status": order_status}).eq("id", e["order_id"]).execute()
        print(f"[{hhmm(clock)}] {e['driver']} · route {e['route_id']} · "
              f"order #{e['order_id']} — {tag}")

    for rid in {e["route_id"] for e in events}:
        sb.table("routes").update({"status": "completed"}).eq("id", rid).execute()
    sb.table("drivers").update({"status": "available"}).eq("status", "on_route").execute()
    print("=== DAY COMPLETE ===")


if __name__ == "__main__":
    run()