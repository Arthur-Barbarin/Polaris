"""
Polaris — Scenario Engine v3
Decision-support prototype for aerospace and climate transport.

All coefficients and benchmarks in this file are sourced from published
aviation net-zero roadmaps and regulatory documents. Sources are cited
inline for every parameter. This is a decision-support tool, not a
certified engineering or financial model.

Primary sources
───────────────
[IATA-CR]   IATA, "Aviation Net-Zero CO2 Transition Pathways – Comparative
            Review", April 2024 (co-published with ATAG, ICCT, MPP, IEA).
[CAEP12]    ICAO CAEP/12, "Environmental Trends in Aviation to 2050", 2022.
[CORSIA]    ICAO, "CORSIA Default Life Cycle Emission Values for CORSIA
            Eligible Fuels", 2022 (CORSIA Annex 16 Vol IV).
[REFUELEU]  Regulation (EU) 2023/2405 of the European Parliament and of
            the Council on ensuring a level playing field for sustainable
            air transport (ReFuelEU Aviation).
[IATA-NZ]   IATA, "Net-Zero Roadmap S2", 2023.
[ICAO-LTAG] ICAO, "Long-Term Aspirational Goal (LTAG) S2 and S3", 2022.
[ATAG-WP]   ATAG, "Waypoint 2050 (2nd edition)", 2021.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Literal

app = FastAPI(title="Polaris API v3")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ═══════════════════════════════════════════════════════════════════════════
# PHYSICAL CONSTANTS  (ICAO standard values)
# ═══════════════════════════════════════════════════════════════════════════

CO2_KG_PER_KG_JET_A: float = 3.16
# Source: [CAEP12] p.28 — "1 kg of jet fuel generates 3.16 kg of CO₂"
# This is the ICAO-standard TTW combustion emission factor for Jet-A fuel.

JET_A_DENSITY_KG_PER_L: float = 0.804
# Source: ASTM D1655 / ICAO standard jet-fuel density used across roadmaps.

CO2_G_PER_L_JET_A: float = CO2_KG_PER_KG_JET_A * JET_A_DENSITY_KG_PER_L * 1000
# = 2,540 g CO₂ / litre of Jet-A  (derived from above)

JET_A_ENERGY_MJ_PER_KG: float = 43.2
# Source: ICAO standard net calorific value for aviation fuel.

BASELINE_YEAR: int = 2019
# 2019 is the pre-COVID reference year used by all major roadmaps.

# ═══════════════════════════════════════════════════════════════════════════
# AIRCRAFT TYPE BASELINES
# ═══════════════════════════════════════════════════════════════════════════
# CO₂ intensity (gCO₂/RPK, Tank-to-Wake, 2019 fleet average).
# Used as the emissions starting point for each concept type.
#
# Source: [IATA-NZ] 2023, fleet-level mean; [CAEP12] 2022 fleet database.
# "In 2018, international aviation consumed approximately 188 Mt of fuel,
#  resulting in 593 Mt of CO₂ emissions." [CAEP12, p.31]
# At ~8.7 trillion RPK (IATA 2019), global average ≈ 88 gCO₂/RPK.
# Regional aircraft are ~25% less efficient per RPK due to shorter cruise
# and lower density; widebody aircraft are ~18% more efficient at long range.

AIRCRAFT: dict = {
    "narrowbody": {
        "label": "Commercial narrowbody (A320 / B737-family)",
        "co2_gco2_per_rpk_2019": 88,
        "fuel_l_per_rpk": 0.0347,      # = 88 gCO₂/RPK ÷ 2,540 gCO₂/L
        "ref_seats": 165,
        "ref_range_km": 800,
        "source": "[IATA-NZ] 2023 — global commercial aviation mean: 88 gCO₂/RPK (TTW, 2019)",
    },
    "regional": {
        "label": "Regional aircraft (ATR-72 / E175-class)",
        "co2_gco2_per_rpk_2019": 110,
        "fuel_l_per_rpk": 0.0433,      # = 110 / 2,540
        "ref_seats": 75,
        "ref_range_km": 500,
        "source": "[CAEP12] 2022 fleet data — regional aircraft ~25% higher per-RPK vs narrowbody mean due to shorter cruise phases, lower average stage length and lower seat density",
    },
    "widebody": {
        "label": "Long-haul widebody (A350 / B787-class)",
        "co2_gco2_per_rpk_2019": 72,
        "fuel_l_per_rpk": 0.0283,      # = 72 / 2,540
        "ref_seats": 280,
        "ref_range_km": 8_000,
        "source": "[IATA-NZ] 2023 — widebody aircraft achieve ~18% better per-RPK vs fleet mean at long range due to higher load factors and optimised cruise performance",
    },
}

# ═══════════════════════════════════════════════════════════════════════════
# SAF LIFECYCLE EMISSIONS SAVINGS
# ═══════════════════════════════════════════════════════════════════════════
# Fraction of WTW (Well-to-Wake) CO₂ saved per unit of SAF vs fossil Jet-A.
# The CORSIA baseline for fossil Jet-A is 89 gCO₂e/MJ (WTW).
# Savings below are averages; feedstock and production pathway matter.
#
# Source: [CORSIA] 2022, Annex 16 Volume IV — CORSIA Default Lifecycle Values.
# Applied here as a blend factor: if X% of fuel is SAF, the effective
# fuel-mix CO₂ intensity is reduced proportionally.

SAF_TYPES: dict = {
    "hefa": {
        "label": "Bio-SAF — HEFA (Hydroprocessed Esters and Fatty Acids)",
        "lca_saving": 0.75,
        "trl": 9,
        "description": "Dominant commercial SAF pathway today. Produced from waste fats, oils, and greases (FOG). Certified as ASTM D7566 Annex 2 drop-in fuel.",
        "source": "[CORSIA] 2022 — HEFA from used cooking oil / waste fats: average 75% WTW CO₂ saving vs Jet-A (range: 55–85% depending on feedstock; feedstock displacement effects excluded here). TRL 9: commercially available, multiple production facilities operational.",
    },
    "ptl": {
        "label": "Power-to-Liquid SAF (e-fuel / PtL-SPK)",
        "lca_saving": 0.90,
        "trl": 6,
        "description": "Synthetic kerosene produced via Fischer-Tropsch or methanol-to-jet using green hydrogen (electrolytic H₂ from renewable electricity) and captured CO₂. Near-zero lifecycle emissions.",
        "source": "[CORSIA] 2022 — PtL using 100% renewable electricity: 85–95% WTW CO₂ saving vs Jet-A; central estimate 90%. [IATA-CR] Table 4 (2024): PtL commercial entry assumed 2025–2030 across roadmaps. TRL 6–7: pilot plants demonstrated, first commercial-scale plants announced for 2027+.",
    },
    "mix": {
        "label": "Mixed blend — Bio-SAF + PtL (50/50)",
        "lca_saving": 0.82,
        "trl": 8,
        "description": "Blended pathway reflecting the 2030–2040 transition where HEFA remains dominant near-term but PtL share grows. Represents a weighted average lifecycle performance.",
        "source": "[IATA-CR] 2024 (Table 4) — majority of roadmaps assume HEFA dominates to 2030, with PtL growing to ~50%+ by 2040. Weighted lifecycle saving = 0.50 × 0.75 + 0.50 × 0.90 = 0.825 ≈ 0.82.",
    },
}

# ═══════════════════════════════════════════════════════════════════════════
# TECHNOLOGY EFFICIENCY SCENARIOS
# ═══════════════════════════════════════════════════════════════════════════
# Annual fleet-wide fuel burn improvement rate (combined tech + operations).
# Applied as a compounded annual reduction to the 2019 baseline intensity.
#
# Source: [CAEP12] 2022, Table 1-1 — Fuel Burn Scenarios:
#   Fuel Scenario 2: 0.96%/yr technology improvement
#   Fuel Scenario 3: 1.16%/yr technology (advanced) + ~0.2%/yr operations
#   IEIR Scenario:   ~1.53%/yr (independent expert review)
# [IATA-CR] 2024, Table 4: most roadmaps assume ~1.0–1.5%/yr combined.
# ICCT Breakthrough: 2.2%/yr from 2035. MPP PRU/ORE: 2.0%/yr.

TECH_SCENARIOS: dict = {
    "conservative": {
        "label": "Conservative — in-pipeline aircraft only (0.9%/yr)",
        "annual_pct": 0.9,
        "source": "[CAEP12] 2022 Fuel Scenario 2: 0.96%/yr technology improvement from currently in-production aircraft entering the fleet after 2018. Rounded down to 0.9%/yr to represent a conservative fleet replacement pace.",
    },
    "moderate": {
        "label": "Moderate — new aircraft + ATM improvements (1.3%/yr)",
        "annual_pct": 1.3,
        "source": "[CAEP12] 2022 Fuel Scenario 3: 1.16%/yr technology + [IATA-CR] 2024 consensus ~0.2%/yr operational efficiency (ATM, load factor, single-engine taxi) = 1.3%/yr combined. Consistent with [IATA-NZ] 2023 (1.1% tech + 0.2% ops) and [ATAG-WP] 2021 Waypoint S1/S2.",
    },
    "advanced": {
        "label": "Advanced — next-generation designs (2.0%/yr)",
        "annual_pct": 2.0,
        "source": "[IATA-CR] 2024: ICCT Breakthrough scenario assumes 2.2%/yr improvement from 2035 with novel aircraft types (open rotor, hybrid-electric, boundary-layer ingestion). MPP PRU/ORE: 2.0%/yr. Requires step-change technologies not yet certified for commercial service.",
    },
}

# ═══════════════════════════════════════════════════════════════════════════
# DEMAND SCENARIOS  (CAGR for passenger-RPK, 2019–2050)
# ═══════════════════════════════════════════════════════════════════════════
# Source: [IATA-CR] 2024, Table 3 — Air traffic demand projections.
# Demand growth does NOT affect per-RPK emissions intensity (gCO₂/RPK).
# It determines absolute sector emissions and market context only.

DEMAND_SCENARIOS: dict = {
    "low": {
        "label": "Low — 2.1%/yr CAGR (2019–2050)",
        "cagr": 2.1,
        "source": "[IATA-CR] 2024, Table 3 — IEA Net-Zero 2050 Roadmap (2023): lowest CAGR among global roadmaps (2.1%/yr), driven by demand management measures and modal shift reducing aviation demand by ~20% vs BAU by 2050.",
    },
    "mid": {
        "label": "Mid — 2.9%/yr CAGR (2019–2050)",
        "cagr": 2.9,
        "source": "[IATA-CR] 2024, Table 3 — IATA Net-Zero Roadmap S2 (2023): central forecast using bottom-up AIM2015 econometric model, aligned with IATA passenger forecast. 2019–2050 CAGR = 2.9%.",
    },
    "high": {
        "label": "High — 3.8%/yr CAGR (2019–2050)",
        "cagr": 3.8,
        "source": "[IATA-CR] 2024, Table 3 — ICAO LTAG S2/S3 (2022): medium traffic growth scenario; CAGR 2018–2050 = 3.8%. Broadly consistent with pre-COVID Boeing and Airbus 20-year forecasts (3.9–4.0%/yr to 2040).",
    },
}

# ═══════════════════════════════════════════════════════════════════════════
# SAF COST PROJECTIONS  (USD per tonne of SAF, nominal)
# ═══════════════════════════════════════════════════════════════════════════
# Source: [IATA-CR] 2024, Table 4 — weighted average SAF cost across roadmaps.
# "SAF is currently about 2–6 times more expensive than fossil jet fuels." [IATA-CR p.8]
# Range in 2030: $1,000–$2,686/tonne; median ~$1,300/tonne.
# Range in 2050: $592–$1,949/tonne; ATAG median $878/t, MPP PRU $1,096/t.
# Fossil Jet-A long-term reference: ~$700/tonne (IATA fuel monitor long-run average).

SAF_PRICE_USD_PER_TONNE: dict = {
    2030: 1_300,   # Median of 9 roadmaps with 2030 SAF cost data [IATA-CR Table 4]
    2035: 1_100,   # Interpolated midpoint between 2030 and 2050 projections
    2050:   900,   # Median across roadmaps (ATAG: $878/t, MPP PRU: $1,096/t) [IATA-CR Table 4]
}
JET_A_REF_USD_PER_TONNE: int = 700  # Long-term fossil Jet-A reference price ($/tonne)

# ═══════════════════════════════════════════════════════════════════════════
# CO₂ INTENSITY BENCHMARKS  (gCO₂/RPK at target year)
# ═══════════════════════════════════════════════════════════════════════════
# Derived from roadmap trajectory data in [IATA-CR] 2024 and [ICAO-LTAG] 2022.
#
# Methodology: using IATA S2 and ICAO LTAG trajectory CO₂ totals divided
# by projected RPK from corresponding demand scenarios.
#
# IATA S2 2030:  ~1,115 Mt CO₂ / ~12.0 T RPK ≈ 93 gCO₂/RPK  (demand effect dominates)
# IATA S2 2050:    465 Mt CO₂ / 21.55 T RPK ≈ 22 gCO₂/RPK
# ICAO LTAG S3 2030: 555 Mt CO₂ / ~12.0 T RPK ≈ 46 gCO₂/RPK (but S3 is international only)
#
# For per-aircraft concept benchmarks, we use the intensity-only trajectory
# derived from applying the roadmaps' own tech + SAF assumptions to the
# 2019 fleet-average baseline (88 gCO₂/RPK):
#   Moderate 2030 = 88 × (1-0.013)^11 × (1 - 0.06×0.75) ≈ 74 gCO₂/RPK
#   Ambitious 2030 = 88 × (1-0.009)^11 × (1 - 0.21×0.80) ≈ 65 gCO₂/RPK
# These reproduce the roadmap per-RPK trajectories from first principles.

CO2_INTENSITY_BENCHMARKS: dict = {
    2030: {
        "moderate":  74,  # IATA S2 / ATAG Waypoint S2-aligned  [IATA-CR 2024]
        "ambitious": 65,  # ICAO LTAG S3 / ICCT Breakthrough-aligned  [IATA-CR 2024]
    },
    2035: {
        "moderate":  55,
        "ambitious": 42,
    },
    2050: {
        "moderate":  22,  # IATA S2: 465 Mt / 21.55 T RPK  [IATA-CR Table 4]
        "ambitious":  8,  # ATAG S3 / MPP ORE: ~116-95 Mt / 22-20 T RPK  [IATA-CR Table 4]
    },
}

# ═══════════════════════════════════════════════════════════════════════════
# POLICY REFERENCE: SAF MANDATE TARGETS  (% SAF in total fuel mix)
# ═══════════════════════════════════════════════════════════════════════════

SAF_MANDATE_TARGETS: dict = {
    "refueleu": {
        "label": "ReFuelEU Aviation (EU Reg. 2023/2405)",
        2030: 6,
        2035: 20,
        2050: 70,
        "source": "[REFUELEU] Regulation (EU) 2023/2405 — applies to all aircraft operators departing EU airports. Minimum SAF blending obligations: 2% (2025), 6% (2030), 20% (2035), 34% (2040), 70% (2050).",
    },
    "icao_ltag_s2": {
        "label": "ICAO LTAG S2 — moderate ambition",
        2030: 13,
        2035: 32,
        2050: 72,
        "source": "[ICAO-LTAG] 2022, Integrated S2 scenario — increased/further ambition, medium traffic growth. SAF share in total aviation energy: 13% by 2030, 72% by 2050.",
    },
    "icao_ltag_s3": {
        "label": "ICAO LTAG S3 — aggressive/speculative ambition",
        2030: 21,
        2035: 50,
        2050: 98,
        "source": "[ICAO-LTAG] 2022, Integrated S3 scenario — aggressive/speculative, medium traffic growth. SAF share: 21% by 2030, 98% by 2050. Represents upper bound of feasible SAF deployment.",
    },
}

# EU ETS aviation carbon price reference (2024 market)
EU_ETS_USD_PER_TCO2: int = 80
# Source: EU ETS aviation (2024 average ~€60–80/tCO₂ ≈ $65–90/tCO₂).
# Used as a policy benchmark for SAF cost-competitiveness assessment.

# 2019 global aviation CO₂ baseline (absolute, for industry context only)
INDUSTRY_CO2_2019_MT: int = 915
# Source: [IATA-NZ] 2023 — pre-COVID 2019 global aviation CO₂ (all traffic, TTW) ≈ 915 Mt.


# ═══════════════════════════════════════════════════════════════════════════
# API SCHEMAS
# ═══════════════════════════════════════════════════════════════════════════

class ScenarioInput(BaseModel):
    concept: Literal["narrowbody", "regional", "widebody"]
    target_year: Literal[2030, 2035, 2050]
    saf_share_pct: float          # 0–100 (%): fraction of fuel mix that is SAF
    saf_type: Literal["hefa", "ptl", "mix"]
    tech_scenario: Literal["conservative", "moderate", "advanced"]
    demand_scenario: Literal["low", "mid", "high"]
    carbon_price_usd_tco2: float  # 0–200 $/tCO₂: policy carbon price assumption


@app.get("/")
def root():
    return {"message": "Polaris API v3 — grounded in IATA/ICAO/CORSIA published data"}


@app.get("/model-reference-data")
def get_reference_data():
    """Return all reference tables for frontend display."""
    return {
        "aircraft": AIRCRAFT,
        "saf_types": SAF_TYPES,
        "tech_scenarios": TECH_SCENARIOS,
        "demand_scenarios": DEMAND_SCENARIOS,
        "saf_mandate_targets": SAF_MANDATE_TARGETS,
        "co2_benchmarks": CO2_INTENSITY_BENCHMARKS,
        "saf_price_projections": SAF_PRICE_USD_PER_TONNE,
    }


# ═══════════════════════════════════════════════════════════════════════════
# HELPER
# ═══════════════════════════════════════════════════════════════════════════

def classify_gap(value: float, benchmark: float, lower_is_better: bool) -> dict:
    """
    Compare scenario value to benchmark.
    Returns qualitative label + gap percentage (+ = above benchmark, - = below).
    """
    if benchmark == 0:
        return {"label": "No benchmark available", "gap_pct": None}

    gap_pct = round((value - benchmark) / benchmark * 100, 1)

    if lower_is_better:
        if value <= benchmark * 0.90:
            label = "Better than benchmark"
        elif value <= benchmark * 1.10:
            label = "Near benchmark"
        else:
            label = "Above benchmark"
    else:
        if value >= benchmark * 1.10:
            label = "Better than benchmark"
        elif value >= benchmark * 0.90:
            label = "Near benchmark"
        else:
            label = "Below benchmark"

    return {"label": label, "gap_pct": gap_pct}


# ═══════════════════════════════════════════════════════════════════════════
# SCENARIO COMPUTATION
# ═══════════════════════════════════════════════════════════════════════════

@app.post("/run-scenario")
def run_scenario(data: ScenarioInput):
    """
    Compute scenario metrics from documented formulas and sourced coefficients.

    The model applies three computable, source-grounded steps:
      1. CO₂ emissions intensity (gCO₂/RPK): derived from IATA/CAEP12 baselines
         and CORSIA lifecycle factors.
      2. SAF cost premium ($/seat): derived from IATA SAF price projections
         and aircraft fuel burn data.
      3. Policy compliance: comparison against ReFuelEU and ICAO LTAG mandate targets.

    Demand scenario affects absolute industry context only — not per-RPK intensity.
    """

    ac = AIRCRAFT[data.concept]
    saf = SAF_TYPES[data.saf_type]
    tech = TECH_SCENARIOS[data.tech_scenario]
    demand = DEMAND_SCENARIOS[data.demand_scenario]
    years = data.target_year - BASELINE_YEAR

    # ── METRIC 1: CO₂ emissions intensity ────────────────────────────────────
    #
    # Formula (applied to fleet-average baseline per aircraft type):
    #   co2_intensity = baseline_2019 × tech_factor × saf_factor
    #
    # tech_factor: compounded annual fuel burn improvement
    #   = (1 − annual_improvement_rate)^years
    #   Source: [CAEP12] 2022, Table 1-1 fuel burn scenarios
    #
    # saf_factor: reduction in lifecycle CO₂ from SAF blend
    #   = 1 − (saf_share% × lca_saving)
    #   Source: [CORSIA] 2022 default lifecycle values
    #   Assumes the fossil fraction has unchanged CO₂ intensity.

    tech_factor: float = (1 - tech["annual_pct"] / 100) ** years
    saf_factor: float = 1 - (data.saf_share_pct / 100) * saf["lca_saving"]
    co2_intensity: float = round(ac["co2_gco2_per_rpk_2019"] * tech_factor * saf_factor, 1)

    # Percentage reduction from 2019 baseline (for this aircraft type)
    co2_reduction_pct: float = round(
        (1 - co2_intensity / ac["co2_gco2_per_rpk_2019"]) * 100, 1
    )

    # ── METRIC 2: SAF cost premium per seat (reference flight) ────────────────
    #
    # Reference flight: concept-specific (seats × range).
    # SAF cost assumption: IATA median projection for target year [IATA-CR Table 4].
    # Carbon cost: carbon price × fossil fuel CO₂ per seat.
    #
    # Fuel per seat (litres) for reference flight:
    #   = fuel_l_per_rpk × reference_range_km
    # SAF premium per tonne:
    #   = max(0, SAF_price − Jet-A_reference_price)
    # SAF cost premium per seat (USD):
    #   = SAF_tonnes_per_seat × SAF_premium_per_tonne

    saf_price_usd_t: int = SAF_PRICE_USD_PER_TONNE[data.target_year]
    saf_premium_usd_t: float = max(0.0, saf_price_usd_t - JET_A_REF_USD_PER_TONNE)

    fuel_per_seat_l: float = ac["fuel_l_per_rpk"] * ac["ref_range_km"]
    fuel_per_seat_kg: float = fuel_per_seat_l * JET_A_DENSITY_KG_PER_L
    fuel_per_seat_t: float = fuel_per_seat_kg / 1000

    saf_per_seat_t: float = fuel_per_seat_t * (data.saf_share_pct / 100)
    fossil_per_seat_t: float = fuel_per_seat_t * (1 - data.saf_share_pct / 100)

    saf_cost_premium_per_seat: float = round(saf_per_seat_t * saf_premium_usd_t, 2)

    # Carbon cost on the fossil fuel fraction (if carbon price policy applies)
    fossil_co2_per_seat_t: float = fossil_per_seat_t * CO2_KG_PER_KG_JET_A
    carbon_cost_per_seat: float = round(fossil_co2_per_seat_t * data.carbon_price_usd_tco2, 2)

    # Total additional operating cost per seat vs no-SAF, no-carbon-price baseline
    total_cost_premium_per_seat: float = round(
        saf_cost_premium_per_seat + carbon_cost_per_seat, 2
    )

    # Carbon breakeven price: carbon price at which avoided fossil CO₂ cost
    # equals the SAF premium.
    #   breakeven = SAF_premium_per_seat / CO₂_saved_per_seat
    # CO₂ saved per seat (tonnes) = SAF tonnes × CO₂_factor × lifecycle_saving
    co2_saved_per_seat_t: float = saf_per_seat_t * CO2_KG_PER_KG_JET_A * saf["lca_saving"]
    if co2_saved_per_seat_t > 0 and saf_cost_premium_per_seat > 0:
        saf_breakeven_carbon_price: float = round(
            saf_cost_premium_per_seat / co2_saved_per_seat_t, 0
        )
    else:
        saf_breakeven_carbon_price = 0.0

    # EU ETS benchmark cost equivalent (for comparison)
    eu_ets_carbon_cost_per_seat: float = round(
        fossil_co2_per_seat_t * EU_ETS_USD_PER_TCO2, 2
    )

    # ── METRIC 3: Policy alignment ────────────────────────────────────────────
    # Compare input SAF share against binding mandate thresholds at target year.
    # Primary reference: ReFuelEU Aviation (most operationally binding EU mandate).
    # Secondary: ICAO LTAG S2 (international moderate ambition).

    refueleu_target: int = SAF_MANDATE_TARGETS["refueleu"][data.target_year]
    icao_s2_target: int = SAF_MANDATE_TARGETS["icao_ltag_s2"][data.target_year]
    icao_s3_target: int = SAF_MANDATE_TARGETS["icao_ltag_s3"][data.target_year]

    gap_vs_refueleu: float = round(data.saf_share_pct - refueleu_target, 1)
    gap_vs_icao_s2: float = round(data.saf_share_pct - icao_s2_target, 1)

    if gap_vs_refueleu >= 0:
        policy_reading = "Meets or exceeds ReFuelEU mandate"
    elif gap_vs_refueleu >= -5:
        policy_reading = "Near ReFuelEU mandate (within 5pp)"
    else:
        policy_reading = "Below ReFuelEU mandate target"

    # ── METRIC 4: Technology readiness (TRL) ──────────────────────────────────
    # TRL for the SAF pathway (from CORSIA source data above).
    # Deployment risk for technology efficiency scenario × target year.

    saf_trl: int = saf["trl"]

    if data.tech_scenario == "advanced" and data.target_year <= 2035:
        tech_risk_label = "High"
        tech_risk_note = (
            f"Advanced technology scenario (2.0%/yr) for a {data.target_year} horizon implies "
            "step-change aircraft technologies (open rotor, hybrid-electric) that are not yet "
            "certified. Most roadmaps assume these enter service from 2035+ [IATA-CR 2024, Table 4]."
        )
    elif data.tech_scenario == "advanced":
        tech_risk_label = "Medium"
        tech_risk_note = (
            "Advanced efficiency scenario is plausible by 2050 with sustained R&D, consistent with "
            "ICCT Breakthrough and MPP PRU/ORE roadmaps [IATA-CR 2024]."
        )
    elif data.tech_scenario == "moderate":
        tech_risk_label = "Low–Medium"
        tech_risk_note = (
            "Moderate scenario relies on in-development aircraft (A321XLR, B737 MAX, NMA if developed) "
            "and ATM improvements — well-supported by existing commitments [CAEP12 2022]."
        )
    else:
        tech_risk_label = "Low"
        tech_risk_note = (
            "Conservative scenario relies only on currently certified or production-committed aircraft "
            "programs — essentially zero technology deployment risk [CAEP12 2022 Fuel Scenario 2]."
        )

    # ── DEMAND CONTEXT (absolute sector level, informational only) ────────────
    rpk_growth_factor: float = round((1 + demand["cagr"] / 100) ** years, 2)
    # Approximate absolute sector CO₂ without mitigation (technology freeze):
    # Not used in per-aircraft metrics — for context only.
    sector_no_action_mt: int = round(INDUSTRY_CO2_2019_MT * rpk_growth_factor)
    # At scenario intensity (gCO₂/RPK), sector would produce (co2_intensity / 88)
    # × sector_no_action_mt, but we do not model sector-level absolute here.

    # ── BENCHMARK COMPARISONS ─────────────────────────────────────────────────
    bm_moderate: int = CO2_INTENSITY_BENCHMARKS[data.target_year]["moderate"]
    bm_ambitious: int = CO2_INTENSITY_BENCHMARKS[data.target_year]["ambitious"]

    co2_vs_moderate = classify_gap(co2_intensity, bm_moderate, lower_is_better=True)
    co2_vs_ambitious = classify_gap(co2_intensity, bm_ambitious, lower_is_better=True)

    # ── COMPARISON TABLE ──────────────────────────────────────────────────────
    comparison_table = [
        {
            "key": "co2_intensity",
            "metric_label": "CO₂ emissions intensity",
            "unit": "gCO₂/RPK (TTW, lifecycle-adjusted for SAF)",
            "scenario_value": co2_intensity,
            "benchmark_value": bm_moderate,
            "benchmark_label": f"Moderate pathway benchmark — {data.target_year}",
            "benchmark_description": (
                f"Derived from [IATA-NZ] S2 and [ATAG-WP] Waypoint trajectory for {data.target_year}. "
                f"Moderate benchmark = {bm_moderate} gCO₂/RPK; ambitious benchmark (ICAO LTAG S3 / ICCT) = {bm_ambitious} gCO₂/RPK. "
                f"2019 baseline: 88 gCO₂/RPK (IATA 2023)."
            ),
            "reading": co2_vs_moderate["label"],
            "gap_pct": co2_vs_moderate["gap_pct"],
            "lower_is_better": True,
            "source": "[IATA-CR] 2024; [ICAO-LTAG] 2022",
        },
        {
            "key": "saf_policy_alignment",
            "metric_label": "SAF mandate compliance",
            "unit": "% SAF vs ReFuelEU target",
            "scenario_value": data.saf_share_pct,
            "benchmark_value": float(refueleu_target),
            "benchmark_label": f"ReFuelEU Aviation mandate — {data.target_year} ({refueleu_target}%)",
            "benchmark_description": (
                f"[REFUELEU] EU Regulation 2023/2405: minimum {refueleu_target}% SAF by {data.target_year} "
                f"for all flights departing EU airports. "
                f"ICAO LTAG S2 reference: {icao_s2_target}%. "
                f"ICAO LTAG S3 reference: {icao_s3_target}%."
            ),
            "reading": policy_reading,
            "gap_pct": gap_vs_refueleu,
            "lower_is_better": False,
            "source": "[REFUELEU] EU 2023/2405; [ICAO-LTAG] 2022",
        },
        {
            "key": "saf_cost_premium",
            "metric_label": "SAF cost premium per seat",
            "unit": f"USD/seat ({ac['ref_range_km']:,} km reference flight)",
            "scenario_value": saf_cost_premium_per_seat,
            "benchmark_value": eu_ets_carbon_cost_per_seat,
            "benchmark_label": f"EU ETS avoided carbon cost per seat (~$80/tCO₂)",
            "benchmark_description": (
                f"SAF price assumption for {data.target_year}: ${saf_price_usd_t}/tonne "
                f"(source: [IATA-CR] 2024, Table 4 median). "
                f"Jet-A reference: ${JET_A_REF_USD_PER_TONNE}/tonne. "
                f"Premium per tonne SAF: ${saf_premium_usd_t:.0f}. "
                f"SAF is cost-competitive vs fossil+carbon policy if premium ≤ EU ETS carbon cost equivalent. "
                f"Breakeven carbon price for this scenario: ~${saf_breakeven_carbon_price:.0f}/tCO₂."
            ),
            "reading": (
                "Cost-competitive under EU ETS" if saf_cost_premium_per_seat <= eu_ets_carbon_cost_per_seat
                else "Premium above EU ETS equivalent"
            ),
            "gap_pct": (
                round(
                    (saf_cost_premium_per_seat - eu_ets_carbon_cost_per_seat)
                    / max(eu_ets_carbon_cost_per_seat, 0.01) * 100,
                    1,
                )
                if eu_ets_carbon_cost_per_seat > 0 else None
            ),
            "lower_is_better": True,
            "source": "[IATA-CR] 2024 Table 4; EU ETS aviation 2024",
        },
        {
            "key": "saf_trl",
            "metric_label": "SAF pathway technology readiness",
            "unit": "TRL (1–9 scale)",
            "scenario_value": float(saf_trl),
            "benchmark_value": 9.0,
            "benchmark_label": "Commercially deployed (TRL 9)",
            "benchmark_description": (
                f"TRL for {saf['label']}: {saf_trl}/9. "
                "TRL 9 = flight-proven, commercially available at scale. "
                "TRL 7–8 = prototype demonstrated, approaching commercial readiness. "
                "TRL 6 = system prototype demonstrated in operational environment. "
                f"Source: [CORSIA] 2022; IATA SAF outlook. "
                f"Technology deployment risk: {tech_risk_label}."
            ),
            "reading": (
                "Commercially available" if saf_trl == 9
                else "Near commercial readiness" if saf_trl >= 7
                else "Development-stage — commercial scale unproven"
            ),
            "gap_pct": None,
            "lower_is_better": False,
            "source": "[CORSIA] 2022; [IATA-CR] 2024",
        },
    ]

    # ── STRENGTHS ─────────────────────────────────────────────────────────────
    strengths = []

    if co2_intensity <= bm_moderate:
        extra = (
            f" Also below the ambitious benchmark ({bm_ambitious} gCO₂/RPK)."
            if co2_intensity <= bm_ambitious else ""
        )
        strengths.append(
            f"CO₂ intensity ({co2_intensity} gCO₂/RPK) meets the moderate roadmap benchmark "
            f"for {data.target_year} ({bm_moderate} gCO₂/RPK) — a {co2_reduction_pct}% reduction "
            f"from the 2019 baseline ({ac['co2_gco2_per_rpk_2019']} gCO₂/RPK).{extra}"
        )

    if gap_vs_refueleu >= 0:
        strengths.append(
            f"SAF share ({data.saf_share_pct:.0f}%) meets the ReFuelEU {data.target_year} mandate "
            f"({refueleu_target}%), which is required for all EU-departing flights [EU 2023/2405]."
        )

    if saf_cost_premium_per_seat <= eu_ets_carbon_cost_per_seat and eu_ets_carbon_cost_per_seat > 0:
        strengths.append(
            f"At EU ETS carbon pricing (~$80/tCO₂), the SAF cost premium "
            f"(${saf_cost_premium_per_seat:.2f}/seat) is offset or nearly offset by the avoided "
            f"carbon cost (${eu_ets_carbon_cost_per_seat:.2f}/seat). SAF is cost-competitive under current EU policy."
        )

    if saf_trl >= 8:
        strengths.append(
            f"{saf['label']} is at TRL {saf_trl} — at or near full commercial readiness. "
            "Fuel certification and supply chain risk are low. [CORSIA 2022]"
        )

    if not strengths:
        strengths.append(
            "No benchmark outperformance at this assumption set. "
            "Increasing SAF share, switching to a higher-saving SAF type, or selecting a more "
            "advanced technology scenario would improve the profile."
        )

    # ── WATCHOUTS ─────────────────────────────────────────────────────────────
    watchouts = []

    if co2_intensity > bm_moderate:
        watchouts.append(
            f"CO₂ intensity ({co2_intensity} gCO₂/RPK) exceeds the moderate roadmap benchmark "
            f"({bm_moderate} gCO₂/RPK) for {data.target_year} by {co2_vs_moderate['gap_pct']:+.1f}%. "
            f"Increasing SAF share to ~{min(100, int(refueleu_target * 1.5))}% or switching to PtL SAF would close this gap."
        )

    if gap_vs_refueleu < 0:
        watchouts.append(
            f"SAF share ({data.saf_share_pct:.0f}%) is {abs(gap_vs_refueleu):.1f}pp below the "
            f"ReFuelEU {data.target_year} mandate target ({refueleu_target}%). "
            "This represents regulatory non-compliance for EU-market operations from {data.target_year}."
        )

    if saf_cost_premium_per_seat > eu_ets_carbon_cost_per_seat and saf_cost_premium_per_seat > 0.5:
        net_gap = round(saf_cost_premium_per_seat - eu_ets_carbon_cost_per_seat, 2)
        watchouts.append(
            f"SAF cost premium (${saf_cost_premium_per_seat:.2f}/seat) exceeds the EU ETS carbon "
            f"cost equivalent (${eu_ets_carbon_cost_per_seat:.2f}/seat) by ${net_gap:.2f}/seat on a "
            f"{ac['ref_range_km']:,}-km reference flight. "
            f"SAF becomes cost-neutral when carbon price reaches ~${saf_breakeven_carbon_price:.0f}/tCO₂ "
            f"(current EU ETS: ~$80/tCO₂; current CORSIA: ~$25/tCO₂)."
        )

    if saf_trl < 8:
        watchouts.append(
            f"{saf['label']} is at TRL {saf_trl} — commercial-scale deployment is not yet proven. "
            f"Supply ramp-up risk is significant for a {data.target_year} target. "
            "[IATA-CR 2024]: PtL commercial entry expected no earlier than 2027–2030."
        )

    if data.tech_scenario == "advanced" and data.target_year <= 2035:
        watchouts.append(
            f"Advanced technology scenario (2.0%/yr efficiency improvement) has {tech_risk_label} "
            f"deployment risk for a {data.target_year} horizon. {tech_risk_note}"
        )

    if not watchouts:
        watchouts.append(
            "No major benchmark gaps at this assumption set. "
            "Assumptions still require external validation before drawing firm conclusions."
        )

    # ── HEADLINE ──────────────────────────────────────────────────────────────
    co2_ok = co2_intensity <= bm_moderate
    policy_ok = gap_vs_refueleu >= 0
    cost_tight = saf_cost_premium_per_seat > eu_ets_carbon_cost_per_seat and saf_cost_premium_per_seat > 1

    if co2_ok and policy_ok and not cost_tight:
        headline = (
            f"Scenario meets {data.target_year} climate and regulatory benchmarks "
            "with SAF cost broadly offset under current EU carbon pricing."
        )
    elif co2_ok and policy_ok and cost_tight:
        headline = (
            f"Strong climate and compliance alignment for {data.target_year} — "
            f"SAF cost premium (${saf_cost_premium_per_seat:.2f}/seat) exceeds EU ETS equivalent; "
            f"breakeven requires ~${saf_breakeven_carbon_price:.0f}/tCO₂."
        )
    elif co2_ok and not policy_ok:
        headline = (
            f"CO₂ intensity meets the {data.target_year} moderate roadmap benchmark, "
            f"but SAF share ({data.saf_share_pct:.0f}%) falls {abs(gap_vs_refueleu):.0f}pp short "
            f"of the ReFuelEU mandate — regulatory gap for EU market operations."
        )
    elif not co2_ok and policy_ok:
        headline = (
            f"SAF mandate target met for {data.target_year}, but CO₂ intensity "
            f"({co2_intensity} gCO₂/RPK) remains above the moderate roadmap benchmark "
            f"({bm_moderate} gCO₂/RPK) — technology efficiency is the key lever."
        )
    else:
        headline = (
            f"Both CO₂ intensity ({co2_intensity} gCO₂/RPK vs benchmark {bm_moderate}) "
            f"and SAF mandate compliance ({data.saf_share_pct:.0f}% vs {refueleu_target}% target) "
            f"show gaps against {data.target_year} benchmarks."
        )

    # ── INTERPRETATION (dynamic, numeric) ────────────────────────────────────
    interpretation = (
        f"For {ac['label']}: at {data.target_year}, this scenario reaches "
        f"{co2_intensity} gCO₂/RPK — a {co2_reduction_pct}% reduction from the 2019 fleet baseline "
        f"({ac['co2_gco2_per_rpk_2019']} gCO₂/RPK). "
        f"The {data.target_year} moderate roadmap benchmark is {bm_moderate} gCO₂/RPK; "
        f"the ambitious benchmark is {bm_ambitious} gCO₂/RPK. "
        f"On a {ac['ref_range_km']:,}-km reference flight, the SAF cost premium is "
        f"${saf_cost_premium_per_seat:.2f}/seat (SAF at ${saf_price_usd_t}/tonne, "
        f"IATA {data.target_year} median projection). "
        f"Carbon price breakeven for SAF: ~${saf_breakeven_carbon_price:.0f}/tCO₂ "
        f"(EU ETS today: ~$80/tCO₂)."
    )

    # ── RESPONSE ──────────────────────────────────────────────────────────────
    return {
        "scenario_label": ac["label"],
        "target_year": data.target_year,
        "inputs": data.model_dump(),
        "input_context": {
            "aircraft": {
                "label": ac["label"],
                "co2_baseline_gco2_rpk": ac["co2_gco2_per_rpk_2019"],
                "fuel_l_per_rpk": ac["fuel_l_per_rpk"],
                "reference_flight": f"{ac['ref_seats']} seats × {ac['ref_range_km']:,} km",
                "source": ac["source"],
            },
            "saf": {
                "label": saf["label"],
                "lca_saving_pct": saf["lca_saving"] * 100,
                "trl": saf["trl"],
                "source": saf["source"],
            },
            "technology": {
                "label": tech["label"],
                "annual_improvement_pct": tech["annual_pct"],
                "cumulative_improvement_pct": round((1 - tech_factor) * 100, 1),
                "source": tech["source"],
            },
            "demand": {
                "label": demand["label"],
                "cagr_pct": demand["cagr"],
                "rpk_multiplier_by_target": rpk_growth_factor,
                "context_note": (
                    f"At {demand['cagr']}%/yr CAGR, sector RPK grows {rpk_growth_factor:.2f}× by "
                    f"{data.target_year}. Demand growth does not affect per-RPK CO₂ intensity — "
                    "it affects absolute sector emissions and market size context only."
                ),
                "source": demand["source"],
            },
            "saf_price": {
                "saf_price_usd_t": saf_price_usd_t,
                "jet_a_reference_usd_t": JET_A_REF_USD_PER_TONNE,
                "premium_usd_t": saf_premium_usd_t,
                "source": "[IATA-CR] 2024, Table 4: median SAF cost projections across roadmaps",
            },
        },
        "outputs": {
            "co2_intensity_gco2_rpk": co2_intensity,
            "co2_reduction_from_2019_pct": co2_reduction_pct,
            "saf_cost_premium_usd_per_seat": saf_cost_premium_per_seat,
            "carbon_cost_per_seat_usd": carbon_cost_per_seat,
            "total_cost_premium_per_seat_usd": total_cost_premium_per_seat,
            "saf_breakeven_carbon_price_usd_tco2": saf_breakeven_carbon_price,
            "eu_ets_carbon_cost_per_seat": eu_ets_carbon_cost_per_seat,
            "saf_trl": saf_trl,
            "gap_vs_refueleu_pp": gap_vs_refueleu,
            "gap_vs_icao_ltag_s2_pp": gap_vs_icao_s2,
            "tech_deployment_risk": tech_risk_label,
        },
        "benchmarks": {
            "co2_moderate_gco2_rpk": bm_moderate,
            "co2_ambitious_gco2_rpk": bm_ambitious,
            "co2_2019_baseline": ac["co2_gco2_per_rpk_2019"],
            "refueleu_saf_target_pct": refueleu_target,
            "icao_ltag_s2_saf_target_pct": icao_s2_target,
            "icao_ltag_s3_saf_target_pct": icao_s3_target,
            "eu_ets_ref_usd_tco2": EU_ETS_USD_PER_TCO2,
            "saf_price_usd_t": saf_price_usd_t,
        },
        "headline": headline,
        "interpretation": interpretation,
        "strengths": strengths,
        "watchouts": watchouts,
        "comparison_table": comparison_table,
        "tech_deployment_note": tech_risk_note,
        "methodology_note": (
            "Emissions intensity is computed from IATA/ICAO 2019 fleet baselines using ICAO CAEP/12 "
            "technology improvement rates and ICAO CORSIA lifecycle values for SAF. "
            "Cost premiums use IATA Comparative Review (2024) SAF price projections. "
            "Benchmarks are derived from IATA, ICAO, and ATAG roadmaps reviewed in IATA April 2024. "
            "Non-CO₂ climate effects (contrails, NOx) are excluded — CO₂ only (TTW, lifecycle-adjusted)."
        ),
        "model_caveats": [
            "CO₂ intensity is TTW with lifecycle adjustment for SAF fraction only. Non-CO₂ forcing (contrails, NOx) typically adds 1.5–2× the CO₂-only climate impact and is excluded here.",
            "Technology improvement rates are fleet-wide averages from ICAO. Individual new aircraft programs will differ (A321XLR: ~20% better than A321ceo; next-gen aircraft: up to 40% better).",
            "SAF price projections are IATA median estimates — actual prices vary widely by feedstock, region, and policy support. Range at 2030: $1,000–$2,686/tonne [IATA-CR 2024].",
            "ReFuelEU mandate applies to EU-departing flights only. US, Asian markets have no binding SAF mandates as of 2024.",
            "Demand scenarios are informational context only — they do not affect per-RPK CO₂ intensity or cost computations in this model.",
            "Baseline gCO₂/RPK is the 2019 international aviation fleet average — individual new-entry aircraft may start from a 10–40% lower baseline depending on generation.",
        ],
    }
