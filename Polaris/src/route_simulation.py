"""
route_simulation.py
-------------------
Physics-informed energy model for multirotor UAVs / eVTOLs.

Theory
------
Power in forward flight has three components (Leishman 2006, Bramwell et al. 2001):

  1. Induced power   — energy needed to accelerate air downward to generate lift.
                       In hover this is dominant; it DECREASES as forward speed
                       increases (the rotor can use a larger air mass).

  2. Profile power   — rotor blade drag. Approximately constant with speed.
                       Typically ~5–8% of hover power for multirotors.

  3. Parasitic power — fuselage + airframe drag. Proportional to V³, so it
                       INCREASES strongly with speed.

The sum of (1) and (3) produces the classic U-shaped power curve:
  · Minimum power at "best endurance" speed (~half the induced velocity)
  · Minimum energy/distance at a higher "best range" speed

Flight profile simulated
------------------------
  Takeoff hover  → Climb → Cruise → Descent → Landing hover

Energy budget
-------------
  E_required  = sum of (power × time) across all phases  [Wh]
  E_available = n_cells × capacity_Ah × voltage_V × SOH  [Wh]
  Margin      = (E_available − E_required) / E_available  [%]
  Decision    = GO if margin ≥ safety_margin_pct, else NO-GO
"""

from __future__ import annotations

import numpy as np
from dataclasses import dataclass, field

# ── Physical constants ────────────────────────────────────────────────────────

G     = 9.81    # gravitational acceleration [m/s²]
RHO0  = 1.225   # ISA sea-level air density  [kg/m³]

# NASA cell characteristics (same cells used in the ML pipeline)
CELL_VOLTAGE_V     = 3.6    # average discharge voltage [V]
CELL_CAPACITY_AH   = 2.0    # nominal capacity [Ah]
CELL_ENERGY_WH     = CELL_VOLTAGE_V * CELL_CAPACITY_AH   # 7.2 Wh per cell

# Rotor efficiency factor (accounts for tip losses, non-uniform inflow, etc.)
# kappa ≈ 1.10–1.20 for multirotors; we use 1.15
KAPPA = 1.15

# ── Dataclasses ───────────────────────────────────────────────────────────────

@dataclass
class VehicleParams:
    """
    Physical properties of the vehicle + payload.

    vehicle_mass_kg       : empty + structure + avionics [kg]
    payload_kg            : cargo / sensors [kg]
    rotor_disk_area_m2    : TOTAL disk area of all rotors [m²]
                            For 4 rotors, each 0.4 m diameter:
                              4 × π × (0.2)² ≈ 0.503 m²
    fuselage_drag_area_m2 : equivalent flat-plate drag area [m²]
                            Typical values: 0.01–0.04 m² for small drones
    n_cells               : number of battery cells in the pack
                            (series + parallel configuration)
    """
    vehicle_mass_kg:      float = 15.0
    payload_kg:           float = 2.0
    rotor_disk_area_m2:   float = 0.50
    fuselage_drag_area_m2: float = 0.020
    n_cells:              int   = 40


@dataclass
class MissionParams:
    """
    Route and flight-profile parameters.

    distance_km      : one-way horizontal distance [km]
    cruise_alt_m     : cruise altitude AGL [m]
    cruise_speed_ms  : horizontal cruise speed [m/s]
    climb_rate_ms    : vertical rate of climb [m/s]
    descent_rate_ms  : vertical rate of descent [m/s]
    hover_time_s     : total hover time at takeoff + landing [s]
    safety_margin    : fraction of battery capacity reserved as margin [0–1]
                       e.g. 0.15 → 15% margin required above computed need
    """
    distance_km:     float = 5.0
    cruise_alt_m:    float = 100.0
    cruise_speed_ms: float = 15.0
    climb_rate_ms:   float = 2.0
    descent_rate_ms: float = 3.0
    hover_time_s:    float = 60.0
    safety_margin:   float = 0.15


@dataclass
class FlightResult:
    """All outputs from simulate_mission()."""
    # Energy by phase [Wh]
    e_hover_wh:    float = 0.0
    e_climb_wh:    float = 0.0
    e_cruise_wh:   float = 0.0
    e_descent_wh:  float = 0.0
    e_total_wh:    float = 0.0

    # Time by phase [s]
    t_hover_s:    float = 0.0
    t_climb_s:    float = 0.0
    t_cruise_s:   float = 0.0
    t_descent_s:  float = 0.0

    # Power [W]
    p_hover_w:   float = 0.0
    p_cruise_w:  float = 0.0
    p_climb_w:   float = 0.0
    p_descent_w: float = 0.0

    # Battery
    e_available_wh: float = 0.0
    e_with_margin_wh: float = 0.0
    margin_pct:     float = 0.0   # (available - required) / available
    go:             bool  = False

    # Derived
    best_range_speed_ms: float = 0.0
    max_range_km:        float = 0.0


# ── Core physics functions ────────────────────────────────────────────────────

def air_density(altitude_m: float) -> float:
    """
    ISA atmosphere air density at altitude [kg/m³].
    Uses the tropospheric lapse rate formula (valid 0–11 km).
    """
    return RHO0 * (1.0 - 2.2558e-5 * altitude_m) ** 4.2559


def hover_power_w(
    total_mass_kg: float,
    rotor_disk_area_m2: float,
    altitude_m: float,
) -> tuple[float, float]:
    """
    Compute ideal hover power and hover induced velocity.

    Momentum theory: thrust T = weight, so
        v_i  = sqrt(T / (2 ρ A))   [induced velocity, m/s]
        P    = κ · T · v_i          [power, W]

    κ (kappa) accounts for real-rotor inefficiencies (tip losses, swirl, etc.).

    Returns
    -------
    (P_hover_w, v_induced_ms)
    """
    rho = air_density(altitude_m)
    W   = total_mass_kg * G
    v_i = np.sqrt(W / (2.0 * rho * rotor_disk_area_m2))
    P   = KAPPA * W * v_i
    return float(P), float(v_i)


def cruise_power_w(
    velocity_ms: float,
    total_mass_kg: float,
    rotor_disk_area_m2: float,
    altitude_m: float,
    fuselage_drag_area_m2: float,
) -> float:
    """
    Total shaft power in forward flight [W].

    Uses the Glauert inflow model (Bramwell, Done & Balmford 2001, §2.4).
    The induced velocity in forward flight satisfies:
        v_i⁴ + V² v_i² − v_h⁴ = 0
    Solving the quadratic in v_i²:
        v_i² = (−V² + √(V⁴ + 4 v_h⁴)) / 2

    Power components:
        P_induced  = κ · T · v_i(V)   — decreases with speed
        P_profile  ≈ 0.06 · P_hover   — blade profile drag, ~constant
        P_parasitic = ½ ρ Cd A V³     — fuselage drag, grows as V³
    """
    rho = air_density(altitude_m)
    W   = total_mass_kg * G
    v_h = np.sqrt(W / (2.0 * rho * rotor_disk_area_m2))   # hover induced vel
    P_hover_ideal = W * v_h                                 # ideal hover power

    V = max(velocity_ms, 0.1)   # avoid division by zero at V≈0

    # Glauert forward-flight induced velocity
    vi_sq     = (-V**2 + np.sqrt(V**4 + 4.0 * v_h**4)) / 2.0
    v_i_fwd   = np.sqrt(max(vi_sq, 0.0))
    P_induced = KAPPA * W * v_i_fwd

    # Profile power (rotor blade drag ≈ constant)
    P_profile = 0.06 * P_hover_ideal

    # Parasitic (fuselage) drag — Cd ≈ 1.0 for flat-plate equivalent area
    P_parasitic = 0.5 * rho * fuselage_drag_area_m2 * V**3

    return float(P_induced + P_profile + P_parasitic)


def power_curve(
    vehicle: VehicleParams,
    altitude_m: float,
    v_max_ms: float = 40.0,
    n_points: int = 200,
) -> tuple[np.ndarray, np.ndarray]:
    """
    Return (speeds, powers) arrays for the power-vs-speed curve.
    Useful for plotting the U-shaped curve and identifying optimal speeds.
    """
    total_mass = vehicle.vehicle_mass_kg + vehicle.payload_kg
    speeds = np.linspace(0.5, v_max_ms, n_points)
    powers = np.array([
        cruise_power_w(v, total_mass, vehicle.rotor_disk_area_m2,
                       altitude_m, vehicle.fuselage_drag_area_m2)
        for v in speeds
    ])
    return speeds, powers


def best_range_speed(vehicle: VehicleParams, altitude_m: float) -> float:
    """
    Best range speed = minimises power/velocity (= energy per unit distance).
    Found by minimising P(V)/V numerically.
    """
    speeds, powers = power_curve(vehicle, altitude_m)
    efficiency = powers / speeds   # W / (m/s) = J/m
    return float(speeds[np.argmin(efficiency)])


# ── Mission simulation ────────────────────────────────────────────────────────

def simulate_mission(
    vehicle: VehicleParams,
    mission: MissionParams,
    battery_soh: float = 1.0,
) -> FlightResult:
    """
    Simulate a point-to-point mission and compute the energy budget.

    Flight profile
    --------------
      1. Hover      : takeoff + pre-flight + landing  [hover_time_s total]
      2. Climb      : vertical climb to cruise_alt_m at climb_rate_ms
      3. Cruise     : horizontal flight at cruise_speed_ms
      4. Descent    : vertical descent from cruise_alt_m at descent_rate_ms

    Power during climb
    ------------------
      P_climb = P_hover + m·g·ROC
      (hover power to maintain altitude, plus extra for gaining potential energy)

    Power during descent
    --------------------
      P_descent ≈ 0.65 · P_hover
      (reducing collective reduces power below hover; ~35% saving on descent)

    Battery available energy
    ------------------------
      E_available = n_cells × CELL_ENERGY_WH × SOH   [Wh]

    GO / NO-GO decision
    -------------------
      GO  if  E_available ≥ E_required × (1 + safety_margin)
    """
    total_mass = vehicle.vehicle_mass_kg + vehicle.payload_kg

    # ── Hover ─────────────────────────────────────────────────────────────────
    P_hover, _ = hover_power_w(
        total_mass, vehicle.rotor_disk_area_m2, altitude_m=0.0)
    t_hover    = mission.hover_time_s
    e_hover    = P_hover * t_hover / 3600.0   # Wh

    # ── Climb ─────────────────────────────────────────────────────────────────
    t_climb  = mission.cruise_alt_m / mission.climb_rate_ms
    P_climb  = P_hover + total_mass * G * mission.climb_rate_ms
    e_climb  = P_climb * t_climb / 3600.0

    # ── Cruise ────────────────────────────────────────────────────────────────
    t_cruise = (mission.distance_km * 1000.0) / mission.cruise_speed_ms
    P_cruise = cruise_power_w(
        mission.cruise_speed_ms, total_mass,
        vehicle.rotor_disk_area_m2, mission.cruise_alt_m,
        vehicle.fuselage_drag_area_m2,
    )
    e_cruise = P_cruise * t_cruise / 3600.0

    # ── Descent ───────────────────────────────────────────────────────────────
    t_descent = mission.cruise_alt_m / mission.descent_rate_ms
    P_hover_cruise, _ = hover_power_w(
        total_mass, vehicle.rotor_disk_area_m2, mission.cruise_alt_m)
    P_descent  = 0.65 * P_hover_cruise
    e_descent  = P_descent * t_descent / 3600.0

    # ── Totals ────────────────────────────────────────────────────────────────
    e_total = e_hover + e_climb + e_cruise + e_descent

    # ── Battery budget ────────────────────────────────────────────────────────
    e_available = vehicle.n_cells * CELL_ENERGY_WH * battery_soh
    e_needed    = e_total * (1.0 + mission.safety_margin)
    margin_pct  = (e_available - e_total) / e_available if e_available > 0 else -1.0
    go          = e_available >= e_needed

    # ── Best range / max range ────────────────────────────────────────────────
    v_best = best_range_speed(vehicle, mission.cruise_alt_m)
    P_best = cruise_power_w(
        v_best, total_mass, vehicle.rotor_disk_area_m2,
        mission.cruise_alt_m, vehicle.fuselage_drag_area_m2,
    )
    # Available energy after hover + climb + descent overhead
    e_for_cruise = e_available - e_hover - e_climb - e_descent
    if P_best > 0 and e_for_cruise > 0:
        t_max_cruise = e_for_cruise * 3600.0 / P_best   # seconds
        max_range_km = v_best * t_max_cruise / 1000.0
    else:
        max_range_km = 0.0

    return FlightResult(
        e_hover_wh=e_hover,
        e_climb_wh=e_climb,
        e_cruise_wh=e_cruise,
        e_descent_wh=e_descent,
        e_total_wh=e_total,
        t_hover_s=t_hover,
        t_climb_s=t_climb,
        t_cruise_s=t_cruise,
        t_descent_s=t_descent,
        p_hover_w=P_hover,
        p_cruise_w=P_cruise,
        p_climb_w=P_climb,
        p_descent_w=P_descent,
        e_available_wh=e_available,
        e_with_margin_wh=e_needed,
        margin_pct=margin_pct,
        go=go,
        best_range_speed_ms=v_best,
        max_range_km=max_range_km,
    )
