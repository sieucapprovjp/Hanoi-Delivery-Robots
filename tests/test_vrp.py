import math
import random
import unittest

from delivery_robots.algorithms.dispatch.vrp_solver import (
    START_NODE_ID,
    build_order_stops,
    check_precedence,
    greedy_initial_solution,
    precompute_distance_matrix,
    relocate_operator,
    sequence_cost,
    solve_vrp_sa,
    swap_operator,
    two_opt_operator,
)


def sample_orders():
    return [
        {
            "id": 1,
            "pickup": {"lat": 21.0, "lon": 105.0, "name": "P1"},
            "dropoff": {"lat": 21.01, "lon": 105.0, "name": "D1"},
        },
        {
            "id": 2,
            "pickup": {"lat": 21.0, "lon": 105.01, "name": "P2"},
            "dropoff": {"lat": 21.01, "lon": 105.01, "name": "D2"},
        },
    ]


def sample_matrix():
    keys = [START_NODE_ID, "P1", "D1", "P2", "D2"]
    matrix = {key: {other: 50.0 for other in keys} for key in keys}
    for key in keys:
        matrix[key][key] = 0.0

    matrix[START_NODE_ID]["P1"] = 1.0
    matrix[START_NODE_ID]["P2"] = 2.0
    matrix["P1"]["P2"] = 1.0
    matrix["P1"]["D1"] = 9.0
    matrix["P2"]["D1"] = 1.0
    matrix["P2"]["D2"] = 2.0
    matrix["D1"]["D2"] = 1.0
    matrix["D2"]["D1"] = 1.0
    return matrix


class VrpSolverTests(unittest.TestCase):
    def test_check_precedence_valid(self):
        stops = build_order_stops(sample_orders())
        sequence = [stops[0], stops[2], stops[1], stops[3]]

        self.assertTrue(check_precedence(sequence))

    def test_check_precedence_invalid(self):
        stops = build_order_stops(sample_orders())
        sequence = [stops[1], stops[0]]

        self.assertFalse(check_precedence(sequence))

    def test_sequence_cost_uses_start_and_stop_order(self):
        stops = build_order_stops(sample_orders())
        sequence = [stops[0], stops[2], stops[1], stops[3]]

        self.assertEqual(sequence_cost(sequence, sample_matrix()), 4.0)

    def test_greedy_initial_solution_returns_valid_sequence(self):
        sequence = greedy_initial_solution(
            {"lat": 21.0, "lon": 105.0}, sample_orders(), sample_matrix()
        )

        self.assertTrue(check_precedence(sequence))
        self.assertEqual(len(sequence), 4)

    def test_operators_preserve_precedence(self):
        rng = random.Random(7)
        sequence = greedy_initial_solution(
            {"lat": 21.0, "lon": 105.0}, sample_orders(), sample_matrix()
        )

        for operator in (swap_operator, relocate_operator, two_opt_operator):
            candidate = operator(sequence, rng)
            self.assertTrue(check_precedence(candidate))
            self.assertEqual(len(candidate), len(sequence))

    def test_solve_vrp_sa_keeps_best_not_worse_than_greedy(self):
        rng = random.Random(42)
        robot_pos = {"lat": 21.0, "lon": 105.0}
        greedy = greedy_initial_solution(robot_pos, sample_orders(), sample_matrix())
        greedy_cost = sequence_cost(greedy, sample_matrix())

        result = solve_vrp_sa(
            robot_pos,
            sample_orders(),
            sample_matrix(),
            params={
                "initial_temp": 50,
                "min_temp": 0.1,
                "cooling_rate": 0.9,
                "iterations_per_temp": 10,
                "max_iterations": 200,
            },
            rng=rng,
        )

        self.assertTrue(result["usedSimulatedAnnealing"])
        self.assertLessEqual(result["finalCost"], greedy_cost)
        self.assertTrue(check_precedence(result["sequence"]))
        self.assertEqual(len(result["sequenceLabels"]), 4)

    def test_single_order_skips_simulated_annealing(self):
        result = solve_vrp_sa(
            {"lat": 21.0, "lon": 105.0},
            sample_orders()[:1],
            sample_matrix(),
            rng=random.Random(1),
        )

        self.assertFalse(result["usedSimulatedAnnealing"])
        self.assertEqual(result["sequenceLabels"], ["P1", "D1"])

    def test_solver_repairs_infinite_greedy_seed(self):
        matrix = sample_matrix()
        matrix["D1"]["P2"] = math.inf
        matrix["P1"]["D1"] = 1.0
        matrix["P1"]["P2"] = 2.0
        matrix["P2"]["D1"] = 1.0
        matrix["D1"]["D2"] = 1.0

        result = solve_vrp_sa(
            {"lat": 21.0, "lon": 105.0},
            sample_orders(),
            matrix,
            params={"min_orders_for_sa": 99},
        )

        self.assertTrue(math.isfinite(result["finalCost"]))
        self.assertTrue(result["stats"]["repairedInitialSequence"])
        self.assertEqual(result["sequenceLabels"], ["P1", "P2", "D1", "D2"])

    def test_precompute_distance_matrix_includes_start(self):
        stops = build_order_stops(sample_orders()[:1])
        matrix = precompute_distance_matrix({"lat": 21.0, "lon": 105.0}, stops)

        self.assertIn(START_NODE_ID, matrix)
        self.assertIn("P1", matrix[START_NODE_ID])
        self.assertGreater(matrix[START_NODE_ID]["D1"], 0)


if __name__ == "__main__":
    unittest.main()
