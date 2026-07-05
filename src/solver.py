"""Step 2.4c — VRP with capacity + time windows + droppable orders."""
from datetime import datetime

from ortools.constraint_solver import pywrapcp, routing_enums_pb2

from src.matrix import get_matrix, load_stops

N_VEHICLES = 4
VEHICLE_CAPACITY_KG = 450


def to_minutes(iso_str: str) -> int:
    dt = datetime.fromisoformat(iso_str)
    return dt.hour * 60 + dt.minute


def solve():
    stops = load_stops()
    matrix = get_matrix(stops)
    n = len(stops)

    manager = pywrapcp.RoutingIndexManager(n, N_VEHICLES, 0)
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
        demand_idx, 0, [VEHICLE_CAPACITY_KG] * N_VEHICLES, True, "Capacity")
    routing.AddDimension(
        transit,
        60,
        24 * 60,
        False,
        "Time")
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
        print("NO SOLUTION — constraints impossible (capacity too small?)")
        return None
    
    total_min, dropped = 0, []
    for node in range(1, n):
        if solution.Value(routing.NextVar(manager.NodeToIndex(node))) == manager.NodeToIndex(node):
            dropped.append(stops[node]["order_id"])
    for v in range(N_VEHICLES):
        index = routing.Start(v)
        route, load, minutes = [], 0, 0
        while not routing.IsEnd(index):
            node = manager.IndexToNode(index)
            if node != 0:
                arrive = solution.Value(time_dim.CumulVar(index))
                route.append(f"#{stops[node]['order_id']}@{arrive//60:02d}:{arrive%60:02d}")
                load += demands[node]
            nxt = solution.Value(routing.NextVar(index))
            minutes += time_cb(index, nxt)
            index = nxt
        total_min += minutes
        print(f"Vehicle {v}: {len(route)} stops, {load}kg, {minutes} min driving")
        print(f"   {route}")
    print(f"TOTAL driving: {total_min} min | DROPPED orders: {dropped or 'none'}")
    return solution


if __name__ == "__main__":
    solve()