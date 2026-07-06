"""VRP solver: capacity + time windows + droppable orders.
Fleet is read from the vehicles table — count and per-vehicle capacities."""
from datetime import datetime

from ortools.constraint_solver import pywrapcp, routing_enums_pb2

from src.db import get_client
from src.matrix import get_matrix, load_stops


def to_minutes(iso_str: str) -> int:
    dt = datetime.fromisoformat(iso_str)
    return dt.hour * 60 + dt.minute


def load_vehicles() -> list[dict]:
    """Only 'active' vehicles work today — maintenance/retired sit out."""
    return (get_client().table("vehicles")
            .select("id, name, capacity_kg")
            .eq("status", "active").order("id").execute().data)


def solve():
    stops = load_stops()
    vehicles = load_vehicles()
    if not vehicles:
        print("NO VEHICLES — the active fleet is empty. Add vehicles first.")
        return None
    matrix = get_matrix(stops)
    n = len(stops)
    k = len(vehicles)
    caps = [int(v["capacity_kg"]) for v in vehicles]
    print(f"Fleet today: {k} vehicles — " +
          ", ".join(f"{v['name']} ({int(v['capacity_kg'])}kg)" for v in vehicles))

    manager = pywrapcp.RoutingIndexManager(n, k, 0)
    routing = pywrapcp.RoutingModel(manager)

    def time_cb(from_index, to_index):
        return matrix[manager.IndexToNode(from_index)][manager.IndexToNode(to_index)]

    transit = routing.RegisterTransitCallback(time_cb)
    routing.SetArcCostEvaluatorOfAllVehicles(transit)

    demands = [0] + [int(round(s["weight_kg"])) for s in stops[1:]]

    def demand_cb(from_index):
        return demands[manager.IndexToNode(from_index)]

    demand_idx = routing.RegisterUnaryTransitCallback(demand_cb)
    routing.AddDimensionWithVehicleCapacity(
        demand_idx, 0, caps, True, "Capacity")

    routing.AddDimension(transit, 60, 24 * 60, False, "Time")
    time_dim = routing.GetDimensionOrDie("Time")
    for node in range(1, n):
        start = to_minutes(stops[node]["window"][0])
        end = to_minutes(stops[node]["window"][1])
        time_dim.CumulVar(manager.NodeToIndex(node)).SetRange(start, end)

    PENALTY = 100_000
    for node in range(1, n):
        routing.AddDisjunction([manager.NodeToIndex(node)], PENALTY)

    params = pywrapcp.DefaultRoutingSearchParameters()
    params.first_solution_strategy = (
        routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC)
    params.local_search_metaheuristic = (
        routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH)
    params.time_limit.FromSeconds(10)

    solution = routing.SolveWithParameters(params)
    if solution is None:
        print("NO SOLUTION — constraints impossible (fleet too small?)")
        return None

    total_min, dropped = 0, []
    for node in range(1, n):
        if solution.Value(routing.NextVar(manager.NodeToIndex(node))) == \
           manager.NodeToIndex(node):
            dropped.append(stops[node]["order_id"])

    plans = []
    for v in range(k):
        index = routing.Start(v)
        route_stops, load, minutes_drv = [], 0, 0
        while not routing.IsEnd(index):
            node = manager.IndexToNode(index)
            if node != 0:
                arrive = solution.Value(time_dim.CumulVar(index))
                route_stops.append({"order_id": stops[node]["order_id"],
                                    "arrive_min": arrive,
                                    "day": stops[node]["window"][0][:10]})
                load += demands[node]
            nxt = solution.Value(routing.NextVar(index))
            minutes_drv += time_cb(index, nxt)
            index = nxt
        total_min += minutes_drv
        plans.append({"vehicle_id": vehicles[v]["id"],
                      "vehicle_name": vehicles[v]["name"],
                      "capacity_kg": caps[v],
                      "stops": route_stops, "load_kg": load,
                      "driving_min": minutes_drv})
        print(f"{vehicles[v]['name']}: {len(route_stops)} stops, "
              f"{load}/{caps[v]}kg, {minutes_drv} min driving")
    print(f"TOTAL driving: {total_min} min | DROPPED orders: {dropped or 'none'}")
    return {"plans": plans, "dropped": dropped}


if __name__ == "__main__":
    solve()