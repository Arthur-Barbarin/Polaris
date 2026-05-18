"""
Polaris — Drone Deployment Decision Engine v1
Sprint 2: Commercial UAS deployment viability analysis.

Answers the question: "Should you deploy drones here, now, and how?"

The tool produces a deployment verdict with an explicit binding constraint label —
telling the user not just whether a scenario fails, but *what specifically* needs
to change to make it viable.

Primary sources
───────────────
[FAA-107]     FAA, 14 CFR Part 107 — Small Unmanned Aircraft Systems,
              effective August 29, 2016; amended December 28, 2020.
[FAA-108]     FAA, Notice of Proposed Rulemaking: Normalizing UAS BVLOS
              Operations (Part 108), Federal Register Vol. 90, Aug 7, 2025.
[FAA-2024]    FAA, CY 2024 Small Unmanned Aircraft Systems Survey Report, 2025.
[DOT-OIG]     DOT OIG, FAA Has Made Progress in Advancing BVLOS Drone
              Operations, June 30, 2025.
[MU-EXT]      University of Missouri Extension, Economics of Drone Ownership
              for Agricultural Spray Applications (G1274), 2024.
[PwC-2016]    PwC, Clarity from Above: PwC Global Report on the Commercial
              Applications of Drone Technology, 2016.
[AUVSI-MAP]   AUVSI, Unmanned Systems Integrated Roadmap 2020-2045, 2020.
[BARCLAYS]    Barclays Equity Research, Drone Delivery Could Unlock $16B in
              Profits, April 2026.
[MANNA-2025]  Manna Drone Delivery, operational and investor disclosures,
              2024-2025.
"""

import json
import os
from typing import Literal, Optional

import groq
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI(title="Polaris Drone Deployment API v1")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ═══════════════════════════════════════════════════════════════════════════
# PLATFORM TIERS
# ═══════════════════════════════════════════════════════════════════════════
# Three tiers abstract the commercial UAS market as of 2024-2025.
# Acquisition costs are midpoints of observed commercial pricing ranges.
# Endurance and range are operational references, not manufacturer maximums.

PLATFORMS: dict = {
    "light": {
        "label": "Light — DJI Mavic 3 Enterprise class",
        "acquisition_cost_usd": 6_500,
        "max_payload_kg": 0.9,
        "endurance_min": 42,
        "cruise_speed_kmh": 45,
        "vlos_max_range_km": 5.0,
        "bvlos_max_range_km": 10.0,
        "battery_set_cost_usd": 300,
        "insurance_annual_usd": 800,
        "ag_coverage_rate_acres_hr": 8,
        "source": (
            "DJI Mavic 3 Enterprise product specifications (2024). "
            "Acquisition cost: $5,000-$8,000 range, midpoint $6,500. "
            "Payload capacity 0.9 kg includes sensor accessories only."
        ),
    },
    "professional": {
        "label": "Professional — DJI Matrice 350 RTK class",
        "acquisition_cost_usd": 20_000,
        "max_payload_kg": 2.7,
        "endurance_min": 55,
        "cruise_speed_kmh": 50,
        "vlos_max_range_km": 8.0,
        "bvlos_max_range_km": 20.0,
        "battery_set_cost_usd": 450,
        "insurance_annual_usd": 2_000,
        "ag_coverage_rate_acres_hr": 13,
        "source": (
            "DJI Matrice 350 RTK product specifications (2024). "
            "Acquisition cost: $15,000-$25,000 range, midpoint $20,000. "
            "Payload includes DJI Zenmuse sensor series (up to 2.7 kg)."
        ),
    },
    "heavy": {
        "label": "Heavy — DJI Matrice 4E / Wingtra ONE GEN II class",
        "acquisition_cost_usd": 50_000,
        "max_payload_kg": 5.0,
        "endurance_min": 57,
        "cruise_speed_kmh": 55,
        "vlos_max_range_km": 12.0,
        "bvlos_max_range_km": 40.0,
        "battery_set_cost_usd": 600,
        "insurance_annual_usd": 4_000,
        "ag_coverage_rate_acres_hr": 20,
        "source": (
            "DJI Matrice 4E and Wingtra ONE GEN II specifications (2024). "
            "Acquisition cost: $35,000-$80,000 range, midpoint $50,000. "
            "BVLOS range 40 km assumes fixed-wing configuration (Wingtra). "
            "Rotary-wing at Heavy tier: effective BVLOS range ~25 km."
        ),
    },
}


# ═══════════════════════════════════════════════════════════════════════════
# ECONOMIC CONSTANTS
# ═══════════════════════════════════════════════════════════════════════════

PILOT_RATE_USD_HR: float = 65.0
# US certified commercial remote pilot (FAA Part 107).
# Range: $55-$80/hr. Source: commercial operator surveys 2024; [FAA-2024].

BATTERY_LIFECYCLE_CYCLES: int = 250
# Conservative central estimate at 80% capacity degradation threshold.
# Range: 200-300 cycles. Source: manufacturer specifications, industry guides.

MAINTENANCE_RATE: float = 0.15
# 15% of platform acquisition cost per year.
# Source: [MU-EXT] 2024; [PwC-2016] methodology for UAS operating cost.

DEPRECIATION_YEARS: int = 3
# Commercial UAS depreciation period for active field operations.
# Source: [MU-EXT] 2024; consistent with accelerated depreciation in US tax code.

SETUP_TIME_HR: float = 0.5
# Pre-flight check + post-flight documentation per mission (all use cases).

VLOS_PRACTICAL_RANGE_KM: float = 1.5
# Practical unaided visual line of sight radius under standard conditions.
# [FAA-107] §107.31 requires VLOS but does not specify a fixed distance.
# 1.5 km is the operational standard accepted by the FAA Safety Team
# and used consistently in published waiver applications.


# ═══════════════════════════════════════════════════════════════════════════
# HUMAN ALTERNATIVE BENCHMARKS
# ═══════════════════════════════════════════════════════════════════════════

HUMAN_ALTERNATIVES: dict = {
    "helicopter": {
        "label": "Manned helicopter patrol",
        "rate_usd_hr": 2_500,
        "patrol_speed_kmh": 60,
        "mobilization_hr": 0.5,
        "source": (
            "[PwC-2016]; helicopter charter industry rates 2024. "
            "Range: $2,000-$3,000/hr (fuel + maintenance + 2 crew + mobilization). "
            "Patrol speed: slow inspection altitude, 60 km/hr."
        ),
    },
    "rope_access": {
        "label": "Rope access inspection team",
        "rate_usd_per_asset": 4_000,
        "source": (
            "Commercial inspection industry data 2024. "
            "Range: $3,000-$5,000 per turbine / industrial structure. "
            "Basis: 2-technician team at $100/hr × 8-12 hr including access setup. "
            "Drone inspection is 60-75% cheaper than rope access. [PwC-2016]"
        ),
    },
    "ground_crew": {
        "label": "Ground crew with bucket truck",
        "rate_usd_hr": 150,
        "patrol_speed_kmh": 2.5,
        "mobilization_hr": 0.5,
        "source": (
            "Utility field operations benchmarks; [PwC-2016]. "
            "Rate: 2-person crew + vehicle + fuel, $150/hr fully loaded. "
            "Coverage speed: 2.5 km/hr along power line infrastructure."
        ),
    },
    "aerial": {
        "label": "Manned agricultural aircraft (crop duster)",
        "rate_usd_per_acre": 15,
        "source": (
            "[MU-EXT] 2024. US manned aerial application rate: $12.50-$20/acre. "
            "Use $15/acre as reference for mixed application types. "
            "Manned aircraft more cost-efficient per acre at very large scale (>5,000 acres/run)."
        ),
    },
    "ground": {
        "label": "Self-propelled ground sprayer",
        "rate_usd_per_acre": 6,
        "source": (
            "[MU-EXT] 2024. Ground sprayer total operating cost including fuel, "
            "labor, and equipment amortization. "
            "Drone advantage over ground: precision (no compaction, no chemical overlap), "
            "hilly/terraced terrain where ground equipment cannot access."
        ),
    },
}

# Delivery: human alternative determined by geography
DELIVERY_COST_PER_STOP: dict = {
    "urban": 6,
    "suburban": 12,
    "rural": 22,
    "remote": 35,
}
# Source: [BARCLAYS] 2026 — $5-7/order in high labor cost markets for autonomous delivery,
# vs $3-7 urban truck, $8-15 suburban, $15-25 rural van. Remote: estimated 1.6× rural.

LABOR_MULTIPLIERS: dict = {
    "low": 0.70,       # Developing / low-wage labor market
    "standard": 1.00,  # US market reference (default)
    "high": 1.50,      # High-cost metro, offshore, remote, union labor
}

# Delivery viability benchmarks
DELIVERY_VIABILITY_THRESHOLD_USD: float = 10.0
# Unit economics must be below $10/delivery to generate margin at scale.
# Source: [BARCLAYS] 2026 — "every major operator arrived at the same $8-12 range."

DELIVERY_PROFITABLE_OPERATOR_USD: float = 4.0
# Manna: ~$4/flight current, targeting $1/delivery at scale. [MANNA-2025]

# Agriculture break-even volume
AGRICULTURE_BREAKEVEN_ACRES_YR: int = 980
# Annual acreage at which drone ownership becomes cost-effective vs contracting.
# Source: [MU-EXT] 2024 — break-even at ~980 acres/yr for owned equipment.

# BVLOS regulatory timeline
PART_108_EXPECTED_YEAR: int = 2027
# FAA Part 108 NPRM published August 7, 2025. Final rule: Spring 2026.
# Implementation (operators can obtain permits): late 2026 to early 2027.
# Source: [FAA-108]; [DOT-OIG] June 2025.


# ═══════════════════════════════════════════════════════════════════════════
# CONSTRAINT LABELS (used in go/no-go output)
# ═══════════════════════════════════════════════════════════════════════════

CONSTRAINT_NONE = "None"
CONSTRAINT_PAYLOAD = "Payload exceeds platform capacity"
CONSTRAINT_RANGE = "Mission range exceeds platform endurance"
CONSTRAINT_BVLOS = "BVLOS required but not authorized"
CONSTRAINT_ECONOMICS = "Drone cost exceeds human alternative"
CONSTRAINT_SCALE = "Insufficient mission volume — high fixed-cost burden"
CONSTRAINT_URBAN = "Urban airspace authorization required (LAANC)"

VERDICT_GO = "GO"
VERDICT_CONDITIONAL = "CONDITIONAL"
VERDICT_NO_GO = "NO-GO"


# ═══════════════════════════════════════════════════════════════════════════
# API SCHEMA
# ═══════════════════════════════════════════════════════════════════════════

class DroneScenarioInput(BaseModel):
    use_case: Literal["inspection", "delivery", "agriculture"]
    # For inspection: helicopter / rope_access / ground_crew
    # For agriculture: aerial / ground
    # For delivery: ignored (auto-derived from geography)
    human_alternative: Literal[
        "helicopter", "rope_access", "ground_crew", "aerial", "ground"
    ] = "helicopter"
    platform_tier: Literal["light", "professional", "heavy"]
    mission_range_km: float          # 0.5–50 km one-way
    payload_kg: float                # 0.1–10 kg
    bvlos_status: Literal["authorized", "waiver_pending", "not_authorized"]
    annual_missions: int             # 10–5000
    geography: Literal["urban", "suburban", "rural", "remote"]
    labor_multiplier: Literal["low", "standard", "high"] = "standard"
    # True for rope_access use case: drone hovers around a point asset (30 min)
    # rather than flying a linear distance
    point_asset_mission: bool = False


# ═══════════════════════════════════════════════════════════════════════════
# COMPUTATION HELPERS
# ═══════════════════════════════════════════════════════════════════════════

def _bvlos_required(mission_range_km: float) -> bool:
    return mission_range_km > VLOS_PRACTICAL_RANGE_KM


def _effective_max_range(platform: dict, bvlos_status: str, bvlos_req: bool) -> float:
    """Return max operational range given current authorization status."""
    if bvlos_req and bvlos_status == "authorized":
        return platform["bvlos_max_range_km"]
    return platform["vlos_max_range_km"]


def _check_constraints(
    platform: dict,
    mission_range_km: float,
    payload_kg: float,
    bvlos_status: str,
    use_case: str,
    geography: str,
) -> tuple[str, str]:
    """
    Run platform and regulatory constraint checks in priority order.
    Returns (binding_constraint_label, verdict).
    Priority: payload > range > regulatory/BVLOS > urban airspace
    """
    bvlos_req = _bvlos_required(mission_range_km)

    # 1 — Payload
    if payload_kg > platform["max_payload_kg"]:
        return CONSTRAINT_PAYLOAD, VERDICT_NO_GO

    # 2 — Range / endurance (check against VLOS limit first, then BVLOS)
    max_range = _effective_max_range(platform, bvlos_status, bvlos_req)
    if mission_range_km > max_range:
        return CONSTRAINT_RANGE, VERDICT_NO_GO

    # 3 — Regulatory BVLOS
    if bvlos_req and bvlos_status == "not_authorized":
        return CONSTRAINT_BVLOS, VERDICT_NO_GO

    if bvlos_req and bvlos_status == "waiver_pending":
        return CONSTRAINT_BVLOS, VERDICT_CONDITIONAL

    # 4 — Urban airspace (delivery only, soft constraint)
    if use_case == "delivery" and geography == "urban":
        return CONSTRAINT_URBAN, VERDICT_CONDITIONAL

    return CONSTRAINT_NONE, VERDICT_GO


def _compute_flight_time(
    platform: dict,
    mission_range_km: float,
    point_asset_mission: bool,
    use_case: str = "other",
) -> float:
    """
    Compute productive flight time in hours.

    - Point asset missions (turbine, tower): fixed 30-min hover inspection.
    - Agriculture: drone uses most of its endurance spraying. Transit to/from
      the field is a small fraction; productive time = 80% of endurance.
      This matches real-world agricultural UAS operations where the drone is
      deployed at the field edge and sprays until battery low.
    - All other use cases: round-trip linear distance / cruise speed.
    """
    if point_asset_mission:
        return 0.5   # 30-min hover inspection per point asset [industry standard]
    if use_case == "agriculture":
        # Productive agricultural flight = 80% of rated endurance (safety margin)
        # Transit is negligible (<5% of total flight) for on-site farm deployment
        endurance_hr = platform["endurance_min"] / 60
        return endurance_hr * 0.8
    return (mission_range_km * 2) / platform["cruise_speed_kmh"]


def _compute_drone_doc(
    platform: dict,
    mission_duration_hr: float,
    annual_missions: int,
) -> dict:
    """
    Compute drone Direct Operating Cost per mission, fully itemised.
    All formulas and sources documented in MODEL_SPRINT2.md §8.3.
    """
    # Fixed costs (scale with annual volume — decrease as volume increases)
    depreciation = platform["acquisition_cost_usd"] / (DEPRECIATION_YEARS * annual_missions)
    maintenance = (platform["acquisition_cost_usd"] * MAINTENANCE_RATE) / annual_missions
    insurance = platform["insurance_annual_usd"] / annual_missions

    # Variable costs (per-mission, volume-independent)
    battery = platform["battery_set_cost_usd"] / BATTERY_LIFECYCLE_CYCLES
    pilot = PILOT_RATE_USD_HR * mission_duration_hr

    total = depreciation + maintenance + insurance + battery + pilot

    return {
        "depreciation": round(depreciation, 2),
        "maintenance": round(maintenance, 2),
        "insurance": round(insurance, 2),
        "battery": round(battery, 2),
        "pilot": round(pilot, 2),
        "total": round(total, 2),
    }


def _compute_human_cost(
    use_case: str,
    human_alternative: str,
    geography: str,
    labor_mult: float,
    mission_range_km: float,
    flight_time_hr: float,
    platform_tier: str,
) -> float:
    """
    Compute the human alternative cost per equivalent mission.
    See MODEL_SPRINT2.md §8.4 for full derivation and sources.
    """
    if use_case == "delivery":
        base = DELIVERY_COST_PER_STOP.get(geography, 12)
        return round(base * labor_mult, 2)

    if use_case == "agriculture":
        ha = HUMAN_ALTERNATIVES[human_alternative]
        rate = ha["rate_usd_per_acre"]
        coverage_rate = PLATFORMS[platform_tier]["ag_coverage_rate_acres_hr"]
        acres_per_mission = coverage_rate * flight_time_hr
        return round(rate * acres_per_mission * labor_mult, 2)

    # Inspection
    ha = HUMAN_ALTERNATIVES[human_alternative]

    if human_alternative == "helicopter":
        coverage_km = mission_range_km * 2
        heli_time = coverage_km / ha["patrol_speed_kmh"] + ha["mobilization_hr"]
        return round(ha["rate_usd_hr"] * heli_time * labor_mult, 2)

    if human_alternative == "rope_access":
        return round(ha["rate_usd_per_asset"] * labor_mult, 2)

    if human_alternative == "ground_crew":
        coverage_km = mission_range_km * 2
        ground_time = coverage_km / ha["patrol_speed_kmh"] + ha["mobilization_hr"]
        return round(ha["rate_usd_hr"] * ground_time * labor_mult, 2)

    return 0.0


def _compute_economics(
    drone_doc: float,
    human_cost: float,
    platform_cost: float,
    annual_missions: int,
) -> dict:
    """Compute savings, break-even, and payback metrics."""
    savings_per_mission = round(human_cost - drone_doc, 2)
    savings_pct = round(savings_per_mission / human_cost * 100, 1) if human_cost > 0 else 0.0
    annual_savings = round(savings_per_mission * annual_missions, 0)

    if savings_per_mission > 0:
        break_even_missions = round(platform_cost / savings_per_mission, 1)
        payback_months = round((break_even_missions / annual_missions) * 12, 1)
    else:
        break_even_missions = None
        payback_months = None

    return {
        "savings_per_mission": savings_per_mission,
        "savings_pct": savings_pct,
        "annual_savings": int(annual_savings),
        "break_even_missions": break_even_missions,
        "payback_months": payback_months,
    }


def _economic_constraint_check(
    drone_doc: float,
    human_cost: float,
    economics: dict,
    annual_missions: int,
) -> tuple[str, str]:
    """
    Check economic viability after all physical/regulatory constraints pass.
    Returns (constraint_label, verdict_override) or (NONE, GO).
    """
    if drone_doc >= human_cost:
        return CONSTRAINT_ECONOMICS, VERDICT_NO_GO

    be = economics["break_even_missions"]
    if be is not None and annual_missions < (be * 0.5):
        return CONSTRAINT_SCALE, VERDICT_CONDITIONAL

    return CONSTRAINT_NONE, VERDICT_GO


def _compute_sensitivity(data: "DroneScenarioInput", base_eco: dict) -> dict:
    """
    Compute three sensitivity sweeps:
      1. Labor cost ±30%: impact on annual savings
      2. Volume ±50% / +100%: impact on annual savings and break-even
      3. BVLOS unlock: additional savings if authorization obtained

    Returns ranked top-3 drivers by absolute annual impact.
    """
    platform = PLATFORMS[data.platform_tier]
    flight_time = _compute_flight_time(
        platform, data.mission_range_km, data.point_asset_mission, data.use_case
    )
    mission_duration = flight_time + SETUP_TIME_HR
    labor_mult_val = LABOR_MULTIPLIERS[data.labor_multiplier]

    # ── Sweep 1: Labor cost ────────────────────────────────────────────────
    labor_results = {}
    for mult_label, delta in [("low (-30%)", 0.70), ("standard", 1.00), ("high (+50%)", 1.50)]:
        hc = _compute_human_cost(
            data.use_case, data.human_alternative, data.geography,
            labor_mult_val * delta,
            data.mission_range_km, flight_time, data.platform_tier,
        )
        doc_items = _compute_drone_doc(platform, mission_duration, data.annual_missions)
        labor_results[mult_label] = {
            "human_cost": hc,
            "annual_savings": int((hc - doc_items["total"]) * data.annual_missions),
        }
    labor_swing = abs(
        labor_results["high (+50%)"]["annual_savings"]
        - labor_results["low (-30%)"]["annual_savings"]
    )

    # ── Sweep 2: Volume ────────────────────────────────────────────────────
    volume_results = {}
    base_hc = _compute_human_cost(
        data.use_case, data.human_alternative, data.geography,
        labor_mult_val, data.mission_range_km, flight_time, data.platform_tier,
    )
    for vol_label, vol_factor in [("half volume", 0.5), ("base volume", 1.0), ("double volume", 2.0)]:
        vol = max(10, int(data.annual_missions * vol_factor))
        doc_items = _compute_drone_doc(platform, mission_duration, vol)
        sav = int((base_hc - doc_items["total"]) * vol)
        volume_results[vol_label] = {
            "annual_missions": vol,
            "drone_doc": doc_items["total"],
            "annual_savings": sav,
        }
    volume_swing = abs(
        volume_results["double volume"]["annual_savings"]
        - volume_results["half volume"]["annual_savings"]
    )

    # ── Sweep 3: BVLOS unlock ──────────────────────────────────────────────
    bvlos_req = _bvlos_required(data.mission_range_km)
    bvlos_unlock_value = 0
    bvlos_note = "Not applicable — mission does not require BVLOS."

    if bvlos_req and data.bvlos_status != "authorized":
        # With BVLOS authorized, the scenario may become viable
        doc_items = _compute_drone_doc(platform, mission_duration, data.annual_missions)
        if base_hc > doc_items["total"]:
            unlocked_savings = int((base_hc - doc_items["total"]) * data.annual_missions)
            current_savings = base_eco.get("annual_savings", 0)
            if current_savings <= 0:
                bvlos_unlock_value = unlocked_savings
                bvlos_note = (
                    f"BVLOS authorization unlocks ${unlocked_savings:,}/yr in savings. "
                    f"Part 108 regulatory pathway: expected 2026-27. [FAA-108]"
                )
            else:
                bvlos_unlock_value = 0
                bvlos_note = "BVLOS waiver pending — savings already included in base scenario."
        else:
            # BVLOS authorization is not the only blocker — economics also fail
            bvlos_unlock_value = 0
            bvlos_note = (
                f"BVLOS authorization required but insufficient alone — drone DOC "
                f"(${doc_items['total']:.2f}/mission) exceeds human alternative "
                f"(${base_hc:.2f}/mission) regardless of authorization. "
                f"Both regulatory authorization and unit economics improvement are needed."
            )
    elif bvlos_req and data.bvlos_status == "authorized":
        bvlos_note = "BVLOS authorized — full range capability already included in base scenario."
    else:
        bvlos_note = "Not applicable — mission operates within VLOS range (≤1.5 km). [FAA-107]"

    # ── Rank top 3 drivers ────────────────────────────────────────────────
    drivers = [
        {
            "driver": "labor_cost",
            "label": "Human alternative labor cost",
            "swing_usd_annual": labor_swing,
            "detail": (
                f"Annual savings range: ${labor_results['low (-30%)']['annual_savings']:,} "
                f"(low labor market) → ${labor_results['high (+50%)']['annual_savings']:,} "
                f"(high labor market). "
                f"Swing: ${labor_swing:,}/yr."
            ),
            "scenarios": labor_results,
        },
        {
            "driver": "mission_volume",
            "label": "Annual mission volume",
            "swing_usd_annual": volume_swing,
            "detail": (
                f"At half volume ({volume_results['half volume']['annual_missions']} missions): "
                f"${volume_results['half volume']['annual_savings']:,}/yr. "
                f"At double volume ({volume_results['double volume']['annual_missions']} missions): "
                f"${volume_results['double volume']['annual_savings']:,}/yr. "
                f"Swing: ${volume_swing:,}/yr."
            ),
            "scenarios": volume_results,
        },
        {
            "driver": "bvlos_unlock",
            "label": "BVLOS regulatory authorization",
            "swing_usd_annual": bvlos_unlock_value,
            "detail": bvlos_note,
            "unlock_value_usd": bvlos_unlock_value,
        },
    ]

    # Sort by absolute impact (descending), keep top 3
    drivers.sort(key=lambda d: d["swing_usd_annual"], reverse=True)

    return {
        "top3_drivers": drivers[:3],
        "labor_sweep": labor_results,
        "volume_sweep": volume_results,
        "bvlos_unlock_usd": bvlos_unlock_value,
        "bvlos_note": bvlos_note,
    }


def _build_resolution_path(
    binding_constraint: str,
    verdict: str,
    economics: dict,
    data: "DroneScenarioInput",
    platform: dict,
) -> str:
    """Build an actionable resolution path for the binding constraint."""

    if verdict == VERDICT_GO:
        return (
            "No blocking constraints. Deployment is viable under current regulatory "
            "and economic parameters."
        )

    if binding_constraint == CONSTRAINT_PAYLOAD:
        return (
            f"Upgrade platform tier. "
            f"Current tier ({data.platform_tier}) max payload: "
            f"{platform['max_payload_kg']} kg; required: {data.payload_kg} kg. "
            f"Next tier up resolves this constraint."
        )

    if binding_constraint == CONSTRAINT_RANGE:
        max_range = _effective_max_range(
            platform, data.bvlos_status, _bvlos_required(data.mission_range_km)
        )
        return (
            f"Upgrade platform tier (current max operational range: {max_range} km; "
            f"required: {data.mission_range_km} km), or deploy intermediate recharge/relay station, "
            f"or segment the mission into multiple shorter flights."
        )

    if binding_constraint == CONSTRAINT_BVLOS:
        if data.bvlos_status == "not_authorized":
            return (
                f"Apply for FAA Part 107 §107.31 BVLOS waiver (FAA target review time: 90 days). "
                f"Alternatively, await Part 108 standardised operating permit framework "
                f"(final rule expected Spring 2026; permits expected 2026-27). [FAA-108] "
                f"Near-term workaround: segment mission to stay within 1.5 km VLOS radius "
                f"with visual observer chain."
            )
        else:
            return (
                "BVLOS waiver application pending FAA review. "
                "Deployment blocked until approval. FAA target review: 90 days. "
                "Part 108 framework (2026-27) will replace per-operation waivers with "
                "operator-level permits. [FAA-108]; [DOT-OIG]"
            )

    if binding_constraint == CONSTRAINT_ECONOMICS:
        return (
            f"Drone DOC (${economics.get('drone_doc', 0):.2f}/mission) exceeds human alternative "
            f"cost (${economics.get('human_cost', 0):.2f}/mission). "
            f"This is uncommon and typically indicates the human alternative is low-cost ground labour. "
            f"Consider: higher-value use case (helicopter vs drone), higher-payload sensor package "
            f"that increases value per mission, or wait for next-generation platform cost reductions."
        )

    if binding_constraint == CONSTRAINT_SCALE:
        be = economics.get("break_even_missions")
        return (
            f"Deployment is economically viable per mission, but current volume "
            f"({data.annual_missions} missions/yr) is below the platform acquisition break-even "
            f"({be:.0f} missions/yr). "
            f"Options: (1) increase contract volume to >{be:.0f} missions/yr, "
            f"(2) use Drone-as-a-Service (DaaS) model to avoid platform acquisition cost, "
            f"(3) share platform across multiple use cases to increase annual utilisation."
        )

    if binding_constraint == CONSTRAINT_URBAN:
        return (
            f"Urban airspace (FAA Class B/C/D or Surface E) requires LAANC authorisation "
            f"or manual FAA DroneZone approval before any flight. [FAA-107] §107.41. "
            f"LAANC is automated and typically approved within minutes via registered UAS apps. "
            f"This is a procedural step, not a permanent barrier — obtain authorisation before deployment."
        )

    return "Review specific constraint above and consult FAA UAS regulatory guidance."


# ═══════════════════════════════════════════════════════════════════════════
# ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════

@app.get("/")
def root():
    return {
        "message": (
            "Polaris Drone Deployment API v1 — "
            "grounded in FAA, PwC, MU Extension, and Barclays published data"
        )
    }


@app.get("/reference-data")
def get_reference_data():
    """Return all reference tables (platforms, benchmarks, rates) for frontend display."""
    return {
        "platforms": PLATFORMS,
        "human_alternatives": HUMAN_ALTERNATIVES,
        "delivery_cost_per_stop": DELIVERY_COST_PER_STOP,
        "labor_multipliers": LABOR_MULTIPLIERS,
        "constants": {
            "pilot_rate_usd_hr": PILOT_RATE_USD_HR,
            "battery_lifecycle_cycles": BATTERY_LIFECYCLE_CYCLES,
            "maintenance_rate_pct": MAINTENANCE_RATE * 100,
            "depreciation_years": DEPRECIATION_YEARS,
            "vlos_practical_range_km": VLOS_PRACTICAL_RANGE_KM,
            "part_108_expected_year": PART_108_EXPECTED_YEAR,
        },
        "benchmarks": {
            "delivery_viability_threshold_usd": DELIVERY_VIABILITY_THRESHOLD_USD,
            "delivery_profitable_operator_usd": DELIVERY_PROFITABLE_OPERATOR_USD,
            "agriculture_breakeven_acres_yr": AGRICULTURE_BREAKEVEN_ACRES_YR,
        },
    }


@app.post("/run-scenario")
def run_scenario(data: DroneScenarioInput):
    """
    Compute drone deployment viability from documented formulas and sourced coefficients.

    Output is structured in three blocks:
      A. Decision signal   — GO / CONDITIONAL / NO-GO with binding constraint
      B. Core metrics      — drone DOC, human cost, savings, break-even
      C. Resolution path   — what changes the verdict + top-3 sensitivity drivers
    """

    platform = PLATFORMS[data.platform_tier]
    labor_mult_val = LABOR_MULTIPLIERS[data.labor_multiplier]
    bvlos_req = _bvlos_required(data.mission_range_km)

    # ── Physical & regulatory constraint checks ────────────────────────────
    binding_constraint, verdict = _check_constraints(
        platform=platform,
        mission_range_km=data.mission_range_km,
        payload_kg=data.payload_kg,
        bvlos_status=data.bvlos_status,
        use_case=data.use_case,
        geography=data.geography,
    )

    # ── Flight time & mission duration ─────────────────────────────────────
    flight_time_hr = _compute_flight_time(
        platform, data.mission_range_km, data.point_asset_mission, data.use_case
    )
    mission_duration_hr = flight_time_hr + SETUP_TIME_HR

    # ── Drone DOC ──────────────────────────────────────────────────────────
    doc_items = _compute_drone_doc(platform, mission_duration_hr, data.annual_missions)
    drone_doc = doc_items["total"]

    # ── Human alternative cost ─────────────────────────────────────────────
    human_alt_label = (
        f"Delivery — {data.geography} van/courier"
        if data.use_case == "delivery"
        else HUMAN_ALTERNATIVES[data.human_alternative]["label"]
    )
    human_cost = _compute_human_cost(
        data.use_case, data.human_alternative, data.geography,
        labor_mult_val, data.mission_range_km, flight_time_hr, data.platform_tier,
    )

    # ── Economic metrics ───────────────────────────────────────────────────
    economics = _compute_economics(
        drone_doc, human_cost, platform["acquisition_cost_usd"], data.annual_missions
    )

    # ── Economic constraint check (only if physical/regulatory passed) ─────
    if verdict == VERDICT_GO:
        econ_constraint, econ_verdict = _economic_constraint_check(
            drone_doc, human_cost, economics, data.annual_missions
        )
        if econ_constraint != CONSTRAINT_NONE:
            binding_constraint = econ_constraint
            verdict = econ_verdict

    # ── Resolution path ────────────────────────────────────────────────────
    resolution_path = _build_resolution_path(
        binding_constraint, verdict, {
            "drone_doc": drone_doc,
            "human_cost": human_cost,
            **economics,
        },
        data, platform,
    )

    # ── Sensitivity analysis ───────────────────────────────────────────────
    sensitivity = _compute_sensitivity(data, economics)

    # ── Benchmark comparison ───────────────────────────────────────────────
    benchmarks = {}

    if data.use_case == "delivery":
        benchmarks = {
            "viability_threshold_usd": DELIVERY_VIABILITY_THRESHOLD_USD,
            "viability_reading": (
                "Below viability threshold — competitive unit economics"
                if drone_doc < DELIVERY_VIABILITY_THRESHOLD_USD
                else "Above viability threshold — cost reduction needed for margin at scale"
            ),
            "profitable_operator_benchmark_usd": DELIVERY_PROFITABLE_OPERATOR_USD,
            "source": "[BARCLAYS] 2026; [MANNA-2025]",
        }

    if data.use_case == "inspection":
        ref_range = HUMAN_ALTERNATIVES.get(data.human_alternative, {})
        benchmarks = {
            "expected_savings_range_pct": {
                "helicopter": "70-80%",
                "rope_access": "60-75%",
                "ground_crew": "20-50%",
            }.get(data.human_alternative, "varies"),
            "actual_savings_pct": economics["savings_pct"],
            "source": "[PwC-2016]; commercial inspection industry data 2024",
        }

    if data.use_case == "agriculture":
        ag_coverage = platform["ag_coverage_rate_acres_hr"]
        acres_per_mission = ag_coverage * flight_time_hr
        annual_acres = acres_per_mission * data.annual_missions
        benchmarks = {
            "breakeven_ownership_acres_yr": AGRICULTURE_BREAKEVEN_ACRES_YR,
            "annual_acres_this_scenario": round(annual_acres, 0),
            "above_breakeven": annual_acres >= AGRICULTURE_BREAKEVEN_ACRES_YR,
            "source": "[MU-EXT] 2024",
        }

    # ── Regulatory context ─────────────────────────────────────────────────
    regulatory_context = {
        "bvlos_required": bvlos_req,
        "vlos_practical_limit_km": VLOS_PRACTICAL_RANGE_KM,
        "bvlos_authorization_status": data.bvlos_status,
        "part_108_status": (
            "NPRM published August 2025. Final rule: Spring 2026. "
            "Operator permits expected 2026-2027."
        ),
        "part_108_source": "[FAA-108]; [DOT-OIG] June 2025",
        "urban_laanc_required": (
            data.use_case == "delivery" and data.geography == "urban"
        ),
    }

    # ── Headline ───────────────────────────────────────────────────────────
    headline = _build_template_headline(
        verdict, binding_constraint, economics, data, drone_doc, human_cost
    )

    # ── Three-block response ───────────────────────────────────────────────
    return {
        # ── BLOCK A: Decision signal ───────────────────────────────────────
        "decision": {
            "verdict": verdict,
            "binding_constraint": binding_constraint,
            "explanation": headline,
            "resolution_path": resolution_path,
        },

        # ── BLOCK B: Core metrics ──────────────────────────────────────────
        "metrics": {
            "drone_doc_per_mission_usd": drone_doc,
            "drone_doc_breakdown": doc_items,
            "human_alternative": human_alt_label,
            "human_cost_per_mission_usd": human_cost,
            "savings_per_mission_usd": economics["savings_per_mission"],
            "savings_pct": economics["savings_pct"],
            "annual_savings_usd": economics["annual_savings"],
            "break_even_missions": economics["break_even_missions"],
            "platform_payback_months": economics["payback_months"],
        },

        # ── BLOCK C: Resolution path + sensitivity ─────────────────────────
        "resolution": {
            "path": resolution_path,
            "sensitivity": sensitivity,
        },

        # ── Supporting context ─────────────────────────────────────────────
        "inputs": data.model_dump(),
        "platform": {
            "tier": data.platform_tier,
            "label": platform["label"],
            "acquisition_cost_usd": platform["acquisition_cost_usd"],
            "max_payload_kg": platform["max_payload_kg"],
            "source": platform["source"],
        },
        "regulatory_context": regulatory_context,
        "benchmarks": benchmarks,
        "methodology_note": (
            "Drone DOC computed from platform depreciation (3-year straight-line), "
            "battery replacement (250-cycle lifecycle), certified remote pilot at $65/hr [FAA-2024], "
            "15% annual maintenance [MU-EXT], and commercial insurance. "
            "Human alternative rates from [PwC-2016], [MU-EXT], and [BARCLAYS] 2026. "
            "BVLOS regulatory references: [FAA-107] §107.31, [FAA-108] Part 108 NPRM, [DOT-OIG] 2025."
        ),
    }


def _build_template_headline(
    verdict: str,
    binding_constraint: str,
    economics: dict,
    data: DroneScenarioInput,
    drone_doc: float,
    human_cost: float,
) -> str:
    """Build a concise template headline as fallback for the LLM narrative."""

    if verdict == VERDICT_GO:
        savings = economics["savings_pct"]
        annual = economics["annual_savings"]
        payback = economics["payback_months"]
        return (
            f"Deployment viable: drone saves {savings:.1f}% per mission "
            f"(${economics['savings_per_mission']:,.2f}/mission), "
            f"${annual:,}/yr at {data.annual_missions} missions. "
            f"Platform payback: {payback:.1f} months."
        )

    if verdict == VERDICT_CONDITIONAL:
        if binding_constraint == CONSTRAINT_BVLOS:
            return (
                f"Deployment blocked pending BVLOS waiver. "
                f"Once authorized, savings of {economics['savings_pct']:.1f}% per mission apply. "
                f"Part 108 framework expected 2026-27. [FAA-108]"
            )
        if binding_constraint == CONSTRAINT_SCALE:
            be = economics["break_even_missions"]
            return (
                f"Economically viable per mission ({economics['savings_pct']:.1f}% savings), "
                f"but volume ({data.annual_missions}/yr) is below the break-even threshold "
                f"({be:.0f} missions/yr). Consider DaaS or higher utilisation."
            )
        return (
            f"Conditional deployment: {binding_constraint}. "
            f"Per-mission economics are viable once constraint is resolved."
        )

    # NO-GO
    return (
        f"Deployment not viable: {binding_constraint}. "
        f"See resolution path for steps to make this scenario viable."
    )


# ═══════════════════════════════════════════════════════════════════════════
# AI LAYER — LLM narrative generation and scenario Q&A
# ═══════════════════════════════════════════════════════════════════════════
# The deterministic computation above is the source of truth.
# These endpoints use an LLM to synthesise structured outputs into
# natural language — they never invent numbers, only interpret them.
#
# Requires: GROQ_API_KEY environment variable.
# Graceful fallback: if key is absent or API call fails, the template
# headline and resolution path from run-scenario are returned unchanged.

def _get_groq_client() -> Optional[groq.Groq]:
    key = os.getenv("GROQ_API_KEY")
    if not key:
        return None
    return groq.Groq(api_key=key)


class NarrativeRequest(BaseModel):
    scenario_result: dict   # Full response from /run-scenario


class ChatMessage(BaseModel):
    role: str        # "user" | "assistant"
    content: str


class ChatRequest(BaseModel):
    question: str
    scenario_context: dict
    history: list[ChatMessage] = []


# ── Prompts ───────────────────────────────────────────────────────────────

_NARRATIVE_SYSTEM = """\
You are an expert commercial drone deployment analyst helping operations managers, \
logistics directors, and infrastructure investors understand the implications of \
scenario model outputs.

The model is grounded in published data: FAA Part 107/108, PwC Clarity from Above (2016), \
University of Missouri Extension economics research (2024), and Barclays drone delivery \
research (2026).

Your job: synthesise quantitative outputs into decision-oriented insight — \
not to restate numbers, but to explain what they mean for a decision-maker.

CRITICAL RULE — every point must answer "so what?": \
what does this number enable, prevent, or imply commercially or operationally?

BAD (restating):  "Drone DOC is $125/mission."
GOOD (interpreting): "At $125 per mission versus $4,000 for rope access, \
the drone recovers its platform cost in under a week — making this one of the \
fastest-payback capital investments in infrastructure maintenance."

BAD (restating):  "BVLOS is not authorized."
GOOD (interpreting): "The BVLOS gap is the single blocking factor here. \
With Part 108 standardised permits expected in 2026-27, this is a dated constraint — \
worth structuring the contract to deploy at scale the moment authorization comes through."

For STRENGTHS: explain WHY the metric matters and what it enables commercially.
For WATCHOUTS: explain what the gap means in practice and what closes it.
For WHAT CHANGES THE DECISION: be specific — name the lever, the threshold, \
and the timeline.

Return ONLY a raw JSON object — no markdown fences, no explanation, no text before or after."""


def _build_narrative_prompt(r: dict) -> str:
    d = r.get("decision", {})
    m = r.get("metrics", {})
    s = r.get("resolution", {}).get("sensitivity", {})
    inp = r.get("inputs", {})
    reg = r.get("regulatory_context", {})
    bm = r.get("benchmarks", {})
    top3 = s.get("top3_drivers", [])
    driver_lines = "\n".join(
        f"  #{i+1} {dr.get('label','')}: swing ${dr.get('swing_usd_annual',0):,}/yr — {dr.get('detail','')}"
        for i, dr in enumerate(top3)
    )

    return f"""Generate a deployment decision narrative for the following Polaris drone scenario.

SCENARIO
  Use case:          {inp.get('use_case', '')} — {m.get('human_alternative', '')}
  Platform:          {r.get('platform', {}).get('label', '')} (${r.get('platform', {}).get('acquisition_cost_usd', 0):,})
  Mission range:     {inp.get('mission_range_km', '')} km one-way
  Annual missions:   {inp.get('annual_missions', '')}
  Geography:         {inp.get('geography', '')}
  BVLOS status:      {inp.get('bvlos_status', '')} (required: {reg.get('bvlos_required', '')})

DECISION SIGNAL
  Verdict:           {d.get('verdict', '')}
  Binding constraint: {d.get('binding_constraint', '')}

CORE METRICS
  Drone DOC/mission: ${m.get('drone_doc_per_mission_usd', 0):.2f}
  Human cost/mission: ${m.get('human_cost_per_mission_usd', 0):.2f} ({m.get('human_alternative', '')})
  Savings/mission:   ${m.get('savings_per_mission_usd', 0):.2f} ({m.get('savings_pct', 0):.1f}%)
  Annual savings:    ${m.get('annual_savings_usd', 0):,}
  Break-even:        {m.get('break_even_missions', 'N/A')} missions
  Payback:           {m.get('platform_payback_months', 'N/A')} months

TOP 3 SENSITIVITY DRIVERS
{driver_lines}

RESOLUTION PATH
  {d.get('resolution_path', '')}

Return this exact JSON structure:
{{
  "headline": "<one sharp sentence, max 20 words — lead with the decision verdict and key economic signal>",
  "interpretation": "<2 sentences: (1) what the combination of verdict + economics means for this operator; (2) the single most important action or lever>",
  "strengths": [
    "<strength: name the metric + explain what it enables commercially or operationally>",
    "<strength: same pattern>",
    "<strength: omit if genuinely only two meaningful strengths>"
  ],
  "watchouts": [
    "<watchout: name the gap + explain what it means in practice + what closes it>",
    "<watchout: same pattern>",
    "<watchout: omit if genuinely only two meaningful watchouts>"
  ],
  "what_changes_the_decision": [
    "<specific lever + threshold + timeline to flip verdict to GO>",
    "<second lever if applicable>"
  ]
}}"""


_CHAT_SYSTEM = """\
You are an expert commercial drone deployment analyst answering follow-up questions \
about a specific scenario run in the Polaris Drone Deployment Decision Engine — a \
quantitative tool grounded in FAA regulations, industry cost benchmarks, and published \
economic research.

Rules:
- Answer only from the scenario context provided. Do not invent numbers.
- Always interpret, not just restate. If a number comes up, explain what it means — \
  compare it to a benchmark, a regulatory threshold, or a real-world decision implication.
- If asked about regulatory timelines (BVLOS, Part 108), be specific: \
  NPRM August 2025, final rule Spring 2026, permits expected 2026-27. [FAA-108]
- If asked about something the model does not compute, say what the model does show \
  that is relevant, and what additional assumption would be needed.
- Keep answers tight: 2-4 sentences. Lead with the insight.
- If the question is outside scope, say so in one sentence then redirect to the most \
  relevant modelled output."""


def _build_context_block(ctx: dict) -> str:
    d = ctx.get("decision", {})
    m = ctx.get("metrics", {})
    inp = ctx.get("inputs", {})
    reg = ctx.get("regulatory_context", {})
    sens = ctx.get("resolution", {}).get("sensitivity", {})
    top3 = sens.get("top3_drivers", [])
    driver_summary = " | ".join(
        f"{dr.get('label','')}: ${dr.get('swing_usd_annual',0):,} swing"
        for dr in top3
    )
    return (
        f"SCENARIO: {inp.get('use_case','')} | {m.get('human_alternative','')} | "
        f"{inp.get('platform_tier','')} platform | {inp.get('mission_range_km','')} km | "
        f"{inp.get('annual_missions','')} missions/yr | {inp.get('geography','')} | "
        f"BVLOS {inp.get('bvlos_status','')}\n"
        f"VERDICT: {d.get('verdict','')} — {d.get('binding_constraint','')}\n"
        f"METRICS: Drone ${m.get('drone_doc_per_mission_usd',0):.2f}/mission vs human "
        f"${m.get('human_cost_per_mission_usd',0):.2f}/mission | "
        f"Savings: {m.get('savings_pct',0):.1f}% | ${m.get('annual_savings_usd',0):,}/yr | "
        f"Break-even: {m.get('break_even_missions','N/A')} missions | "
        f"Payback: {m.get('platform_payback_months','N/A')} months\n"
        f"BVLOS required: {reg.get('bvlos_required','')} | "
        f"Part 108: final rule Spring 2026, permits expected 2026-27 [FAA-108]\n"
        f"TOP DRIVERS: {driver_summary}\n"
        f"RESOLUTION: {d.get('resolution_path','')}"
    )


# ── Endpoints ─────────────────────────────────────────────────────────────

@app.post("/generate-narrative")
def generate_narrative(req: NarrativeRequest):
    """
    Generate LLM-authored headline, interpretation, strengths, watchouts,
    and what-changes-the-decision for a completed scenario result.
    Falls back to template strings if Groq is unavailable.
    """
    client = _get_groq_client()

    if not client:
        d = req.scenario_result.get("decision", {})
        return {
            "ai_available": False,
            "headline": d.get("explanation", ""),
            "interpretation": d.get("resolution_path", ""),
            "strengths": [],
            "watchouts": [],
            "what_changes_the_decision": [d.get("resolution_path", "")],
        }

    try:
        msg = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            max_tokens=1_024,
            messages=[
                {"role": "system", "content": _NARRATIVE_SYSTEM},
                {"role": "user",   "content": _build_narrative_prompt(req.scenario_result)},
            ],
        )
        parsed = json.loads(msg.choices[0].message.content.strip())
        return {
            "ai_available": True,
            "headline":                   parsed.get("headline", ""),
            "interpretation":             parsed.get("interpretation", ""),
            "strengths":                  parsed.get("strengths", []),
            "watchouts":                  parsed.get("watchouts", []),
            "what_changes_the_decision":  parsed.get("what_changes_the_decision", []),
        }
    except Exception as exc:
        d = req.scenario_result.get("decision", {})
        return {
            "ai_available": False,
            "headline":                  d.get("explanation", ""),
            "interpretation":            d.get("resolution_path", ""),
            "strengths":                 [],
            "watchouts":                 [],
            "what_changes_the_decision": [d.get("resolution_path", "")],
            "error": str(exc),
        }


@app.post("/chat")
def chat(req: ChatRequest):
    """
    Answer a natural-language question about a drone deployment scenario.
    The full scenario context is embedded in the prompt — no database needed.
    """
    client = _get_groq_client()

    if not client:
        return {
            "ai_available": False,
            "reply": (
                "AI chat is not available. "
                "Set the GROQ_API_KEY environment variable to enable it."
            ),
        }

    context_block = _build_context_block(req.scenario_context)

    messages = [{"role": "system", "content": _CHAT_SYSTEM}]
    for turn in req.history[-6:]:
        messages.append({"role": turn.role, "content": turn.content})
    messages.append({
        "role": "user",
        "content": f"{context_block}\n\nQUESTION: {req.question}",
    })

    try:
        resp = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            max_tokens=512,
            messages=messages,
        )
        return {
            "ai_available": True,
            "reply": resp.choices[0].message.content.strip(),
        }
    except Exception as exc:
        return {
            "ai_available": False,
            "reply": "Sorry, I couldn't generate a response. Please try again.",
            "error": str(exc),
        }
