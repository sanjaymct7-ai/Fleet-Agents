"""Step 3.2 — Dispatch agent: assign planned routes to available drivers.
Rules only, no LLM: read routes+drivers, write assignments+statuses."""
from src.db import get_client


def hhmm_to_min(t: str) -> int:
    h, m = t.split(":")
    return int(h) * 60 + int(m)


def route_span(sb, route_id: int) -> tuple[int, int]:
    """(first_arrival, last_arrival) in minutes-since-midnight."""
    stops = (sb.table("route_stops").select("planned_arrival")
             .eq("route_id", route_id).order("seq").execute().data)
    times = [int(s["planned_arrival"][11:13]) * 60 + int(s["planned_arrival"][14:16])
             for s in stops]
    return min(times), max(times)


def dispatch():
    sb = get_client()
    routes = sb.table("routes").select("id").eq("status", "planned").execute().data
    drivers = sb.table("drivers").select("*").eq("status", "available").execute().data
    if not routes:
        print("No planned routes to dispatch.")
        return

    for route in routes:
        first, last = route_span(sb, route["id"])
        chosen = None
        for d in drivers:
            fits_shift = (hhmm_to_min(d["shift_start"]) <= first
                          and last <= hhmm_to_min(d["shift_end"]))
            fits_hours = (last - first) <= d["max_hours"] * 60
            if fits_shift and fits_hours:
                chosen = d
                break

        if chosen is None:
            print(f"Route {route['id']}: NO ELIGIBLE DRIVER — raising exception")
            try:
                sb.table("exceptions").insert({
                    "type": "no_driver", "route_id": route["id"],
                    "detail": f"no driver fits route span "
                              f"{first//60:02d}:{first%60:02d}-{last//60:02d}:{last%60:02d}",
                }).execute()
            except Exception:
                pass   # unique-rail duplicate — already raised
            continue

        sb.table("routes").update({"driver_id": chosen["id"], "status": "assigned"}) \
          .eq("id", route["id"]).execute()
        sb.table("drivers").update({"status": "on_route"}).eq("id", chosen["id"]).execute()
        order_ids = [s["order_id"] for s in sb.table("route_stops")
                     .select("order_id").eq("route_id", route["id"]).execute().data]
        sb.table("orders").update({"status": "assigned"}).in_("id", order_ids).execute()
        drivers.remove(chosen)
        print(f"Route {route['id']} ({first//60:02d}:{first%60:02d}-"
              f"{last//60:02d}:{last%60:02d}) -> {chosen['name']}")


if __name__ == "__main__":
    dispatch()