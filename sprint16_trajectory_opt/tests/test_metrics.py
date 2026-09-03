import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from traj import TrajectoryProblem, solve_trajectory, benefit, corridor_sweep
from traj.metrics import analytic_rms

P = TrajectoryProblem()
SOL = solve_trajectory(P, include_path_constraints=True)
BEN = benefit(P)


def test_solution_converges_and_is_feasible():
    assert SOL.converged
    assert SOL.feasible
    assert SOL.terminal_error < 1e-2


def test_constraints_are_respected():
    assert SOL.min_floor_clearance > -1e-3
    assert SOL.min_corridor_clearance > -1e-3
    assert SOL.max_accel <= max(P.ax_max, P.ah_max) + 1e-3


def test_saving_vs_bangbang_is_25_percent():
    # exact for a rest-to-rest double integrator: 12/16 -> 25%
    assert abs(BEN.savings_fraction - 0.25) < 0.01


def test_noise_corridor_costs_energy():
    assert BEN.price_of_noise > 0
    assert BEN.energy_with_corridor > BEN.energy_optimal


def test_unconstrained_matches_analytic():
    assert analytic_rms(P) < 0.05


def test_corridor_energy_is_monotone():
    energies = [e for _, e in corridor_sweep(P, [160, 180, 200, 220, 240, 260])]
    assert all(energies[i] <= energies[i + 1] + 1e-6 for i in range(len(energies) - 1))


def test_deterministic():
    again = solve_trajectory(P, include_path_constraints=True)
    assert abs(again.energy - SOL.energy) < 1e-6
