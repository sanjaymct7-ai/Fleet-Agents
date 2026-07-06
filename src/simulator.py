"""Simulation engine: plays out the day in accelerated time,
injects reality (traffic, lateness, failed deliveries),
and publishes live GPS positions for the Command Center map."""
import random
import time

from src.db import get_client
from src.matrix import DEPOT

SPEED = 0.1           # real seconds per simulated minute
random.seed()         # set a number, e.g. random.seed(42), for repeatable days

# --- the reality model (the chaos dials) ---
P_TRAFFIC_PER_ROUTE = 0.30    # chance a route hits a traffic jam somewhere
TRAFFIC_DELAY = (15, 40)      # minutes added to every remaining stop
P_STOP_LATE = 0.20            # chance an individual stop slips
STOP_DELAY = (5, 25)
P_DELIVERY_FAILS = 0.10       # nobody home / wrong address


def hhmm(m):
    return f"{m // 60:02d}:{m % 60:02d}"


# ---------------- world loading ----------------
def load_day(sb):
    """Assigned routes -> list of stop-events sorted by planned time."""
    routes = (sb.table("routes").select("id, driver_id, drivers(name)")
              .eq("status", "assigned").execute().data)
    events = []
    for r in routes:
        stops = (sb.table("route_stops")
                 .select("id, order_id, seq, planned_arrival, "
                         "orders(drop_lat, drop_lng)")
                 .eq("route_id", r["id"]).order("seq").execute().data)
        for s in stops:
            planned = (int(s["planned_arrival"][11:13]) * 60
                       + int(s["planned_arrival"][14:16]))
            events.append({"route_id": r["id"], "driver": r["drivers"]["name"],
                           "stop_id": s["id"], "order_id": s["order_id"],
                           "seq": s["seq"], "planned": planned,
                           "day": s["planned_arrival"][:10],
                           "coord": (float(s["orders"]["drop_lat"]),
                                     float(s["orders"]["drop_lng"]))})
    return sorted(events, key=lambda e: e["planned"])


# ---------------- reality injection ----------------
def inject_reality(events):
    """Decide, per route and per stop, what ACTUALLY happens."""
    delays = {}  # route_id -> (from_seq, minutes) traffic jam
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


# ---------------- fake GPS ----------------
def build_tracks(events):
    """route_id -> ordered waypoints [(minute, (lat, lng))]. Depot first."""
    tracks = {}
    for e in sorted(events, key=lambda e: e["actual"]):
        rid = e["route_id"]
        if rid not in tracks:
            tracks[rid] = [(e["actual"] - 20, DEPOT)]  # left depot ~20 min earlier
        tracks[rid].append((e["actual"], e["coord"]))
    return tracks


def position_at(track, minute):
    """Linear interpolation between waypoints = fake GPS."""
    if minute <= track[0][0]:
        return track[0][1]
    for (t1, p1), (t2, p2) in zip(track, track[1:]):
        if t1 <= minute <= t2:
            f = 0 if t2 == t1 else (minute - t1) / (t2 - t1)
            return (p1[0] + (p2[0] - p1[0]) * f,
                    p1[1] + (p2[1] - p1[1]) * f)
    return track[-1][1]


def publish_positions(sb, tracks, drivers_by_route, clock):
    rows = [{"route_id": rid,
             "driver_name": drivers_by_route[rid],
             "lat": pos[0], "lng": pos[1], "sim_time": hhmm(clock)}
            for rid, track in tracks.items()
            if (pos := position_at(track, clock))]
    if rows:
        sb.table("vehicle_positions").upsert(rows).execute()


# ---------------- the day itself ----------------
def run():
    sb = get_client()
    events = inject_reality(load_day(sb))
    if not events:
        print("Nothing to simulate — dispatch some routes first.")
        return

    tracks = build_tracks(events)
    drivers_by_route = {e["route_id"]: e["driver"] for e in events}
    sb.table("vehicle_positions").delete().neq("route_id", 0).execute()

    clock = events[0]["actual"]
    print(f"=== DAY BEGINS at {hhmm(clock)} — {len(events)} deliveries scheduled ===")
    for e in events:
        while clock < e["actual"]:
            clock += 1
            if clock % 3 == 0:
                publish_positions(sb, tracks, drivers_by_route, clock)
            time.sleep(SPEED)

        gap = e["actual"] - e["planned"]
        if e["failed"]:
            status, order_status = "failed", "failed"
            tag = "❌ DELIVERY FAILED (nobody home)"
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