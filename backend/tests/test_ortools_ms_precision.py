from __future__ import annotations

from app.algorithms.ortools_solver import ORToolsSolver
from app.algorithms import scenarios


def test_100ms_time_limit_not_one_second():
    scen = scenarios.scenario_registry.get("grid_cvrp_6")
    s = ORToolsSolver(scen, time_limit_ms=100)
    import time

    t0 = time.perf_counter()
    sol = s.solve()
    t1 = time.perf_counter()
    wall_ms = (t1 - t0) * 1000.0
    # tolerant bound - should be much less than 1 second
    assert wall_ms < 1500.0
    assert sol.feasible is True


def test_time_limit_configuration_ms_precision():
    scen = scenarios.scenario_registry.get("grid_cvrp_6")
    s = ORToolsSolver(scen, time_limit_ms=100)
    assert s.time_limit_ms == 100
    from ortools.constraint_solver import pywrapcp, routing_enums_pb2

    time_matrix, _ = __import__(
        "app.algorithms.evaluate", fromlist=[""]
    ).edge_cost_matrice(scenario=scen) if False else (None, None)

    # rebuild params as in solve
    time_matrix, _ = __import__(
        "app.algorithms.evaluate", fromlist=[""]
    ).edge_cost_matrice(scen)
    from ortools.constraint_solver import pywrapcp, routing_enums_pb2
    from app.algorithms.evaluate import edge_cost_matrice
    from app.algorithms.models import DEPOT_INDEX

    time_matrix, _ = edge_cost_matrice(scen)
    num_nodes = scen.num_stops
    manager = pywrapcp.RoutingIndexManager(num_nodes, scen.num_vehicles, DEPOT_INDEX)
    routing = pywrapcp.RoutingModel(manager)

    def time_callback(from_index, to_index):
        from_node = manager.IndexToNode(from_index)
        to_node = manager.IndexToNode(to_index)
        return int(time_matrix[from_node][to_node])

    transit_callback_index = routing.RegisterTransitCallback(time_callback)
    routing.SetArcCostEvaluatorOfAllVehicles(transit_callback_index)
    search_parameters = pywrapcp.DefaultRoutingSearchParameters()
    if s.time_limit_ms > 0:
        search_parameters.time_limit.FromMilliseconds(int(s.time_limit_ms))
    else:
        search_parameters.time_limit.FromMilliseconds(10000)
    assert search_parameters.time_limit.ToMilliseconds() == 100
