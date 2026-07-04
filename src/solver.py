"""Step 2.4b — VRP with capacity. Time windows arrive in 2.4c."""
from ortools.constraint_solver import pywrapcp, routing_enums_pb2

from src.matrix import get_matrix, load_stops

N_VEHICLES = 4
VEHICLE_CAPACITY_KG = 450

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

    total_min = 0
    for v in range(N_VEHICLES):
        index = routing.Start(v)
        route, load, minutes = [], 0, 0
        while not routing.IsEnd(index):
            node = manager.IndexToNode(index)
            if node != 0:
                route.append(stops[node]["order_id"])
                load += demands[node]
            nxt = solution.Value(routing.NextVar(index))
            minutes += time_cb(index, nxt)
            index = nxt
        total_min += minutes
        print(f"Vehicle {v}: {len(route)} stops, {load}kg, {minutes} min")
        print(f"   orders: {route}")
    print(f"TOTAL fleet driving time: {total_min} minutes")
    return solution


if __name__ == "__main__":
    solve()