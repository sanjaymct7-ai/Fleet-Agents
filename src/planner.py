"""Step 2.5 — Route Planning agent's write permission:
persist solver output into routes + route_stops, mark orders planned.
Now records which vehicle drove each route."""
from src.db import get_client
from src.solver import solve


def minutes_to_ts(day: str, minutes: int) -> str:
    return f"{day}T{minutes // 60:02d}:{minutes % 60:02d}:00"


def plan_and_save():
    result = solve()
    if result is None:
        print("Nothing to save — solver found no solution.")
        return
    sb = get_client()

    # Idempotent re-planning: clear previous plan (stops first — FK order!)
    sb.table("route_stops").delete().neq("id", 0).execute()
    sb.table("routes").delete().neq("id", 0).execute()

    planned_order_ids = []
    for plan in result["plans"]:
        if not plan["stops"]:
            continue  # empty vehicle: no route row needed
        route = sb.table("routes").insert({
            "vehicle_id": plan["vehicle_id"],
            "vehicle_capacity_kg": plan["capacity_kg"],
            "status": "planned",
        }).execute().data[0]

        stop_rows = [{
            "route_id": route["id"],
            "order_id": s["order_id"],
            "seq": i + 1,
            "stop_type": "dropoff",
            "planned_arrival": minutes_to_ts(s["day"], s["arrive_min"]),
        } for i, s in enumerate(plan["stops"])]
        sb.table("route_stops").insert(stop_rows).execute()
        planned_order_ids += [s["order_id"] for s in plan["stops"]]
        print(f"Saved route {route['id']} ({plan['vehicle_name']}): {len(stop_rows)} stops")

    if planned_order_ids:
        sb.table("orders").update({"status": "planned"}) \
          .in_("id", planned_order_ids).execute()
    print(f"{len(planned_order_ids)} orders marked 'planned'. "
          f"Dropped (still 'new'): {result['dropped'] or 'none'}")


if __name__ == "__main__":
    plan_and_save()