from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Literal


app = FastAPI(title="Polaris API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ScenarioInput(BaseModel):
    concept: Literal["regional", "narrowbody", "drone"]
    saf_share: float          # 0–100, percent of fuel mix that is SAF
    hydrogen_readiness: float # 0–100, heuristic technology maturity index
    electricity_price: float  # 0–100, relative electricity cost exposure index
    carbon_price: float       # 0–200, $/tCO2 equivalent policy signal
    demand_growth: float      # 0–100, relative demand growth signal index


@app.get("/")
def root():
    return {"message": "Polaris API is running"}


def classify_gap(value: float, benchmark: float, lower_is_better: bool) -> dict:
    """
    Compare a scenario metric value to a benchmark.
    Returns a qualitative label and a gap percentage (+ = above benchmark, - = below).
    """
    if benchmark == 0:
        return {"label": "No benchmark available", "gap_pct": None}

    gap_pct = round((value - benchmark) / benchmark * 100, 1)

    if lower_is_better:
        if value <= benchmark * 0.9:
            label = "Better than benchmark"
        elif value <= benchmark * 1.1:
            label = "Near benchmark"
        else:
            label = "Above benchmark"
    else:
        if value >= benchmark * 1.1:
            label = "Better than benchmark"
        elif value >= benchmark * 0.9:
            label = "Near benchmark"
        else:
            label = "Below benchmark"

    return {"label": label, "gap_pct": gap_pct}


def generate_interpretation(concept_label: str, reading_labels: dict, outputs: dict) -> str:
    """
    Dynamically generate a scenario-specific interpretation
    based on the actual benchmark readings for this run.
    """
    strong = []
    weak = []

    if reading_labels["emissions_index"] == "Better than benchmark":
        strong.append("climate emissions performance")
    if reading_labels["adoption_index"] in ["Near benchmark", "Better than benchmark"]:
        strong.append("commercial traction potential")
    if reading_labels["cost_pressure_index"] == "Better than benchmark":
        strong.append("cost position")

    if reading_labels["technical_risk_index"] == "Above benchmark":
        weak.append("technical readiness (risk index remains elevated)")
    if reading_labels["cost_pressure_index"] == "Above benchmark":
        weak.append("cost pressure (above kerosene baseline reference)")
    if reading_labels["adoption_index"] == "Below benchmark":
        weak.append("adoption potential (below strong commercial traction reference)")

    if strong and weak:
        return (
            f"For {concept_label}: the scenario shows positive signals on "
            f"{', '.join(strong)}, but faces open questions on {', '.join(weak)}."
        )
    elif strong and not weak:
        return (
            f"For {concept_label}: the scenario is directionally strong across "
            f"{', '.join(strong)}. No major benchmark gaps stand out — "
            f"though all assumptions still need external validation."
        )
    elif weak and not strong:
        return (
            f"For {concept_label}: the scenario shows no clear benchmark advantages "
            f"and faces open questions on {', '.join(weak)}. "
            f"Revisiting input assumptions may shift the picture."
        )
    else:
        return (
            f"For {concept_label}: the scenario sits broadly near all benchmark references. "
            "No dominant strengths or critical gaps are visible at this assumption set."
        )


@app.post("/run-scenario")
def run_scenario(data: ScenarioInput):
    """
    Polaris scenario engine — illustrative prototype only.

    Translates user assumptions → indexed outputs → benchmark comparisons → interpretation.
    This is NOT a certified engineering or financial model.
    All coefficients are heuristic and illustrative.
    """

    # ── Concept modifiers ─────────────────────────────────────────────────────
    # Multipliers adjust baseline metric levels per concept archetype.
    # These are heuristic adjustments, not calibrated from real fleet data.
    concept_factors = {
        "regional": {
            "label": "Regional aircraft",
            "capex_pressure": 1.0,
            "complexity": 1.0,
            "adoption_boost": 1.0,
        },
        "narrowbody": {
            "label": "Low-emission narrowbody",
            "capex_pressure": 1.1,   # higher certification and integration burden
            "complexity": 1.2,       # more complex propulsion integration
            "adoption_boost": 0.9,   # slower fleet turnover expected
        },
        "drone": {
            "label": "Advanced air mobility / drone",
            "capex_pressure": 0.75,  # lower unit-level CAPEX
            "complexity": 0.8,       # simpler airframe relative to commercial aviation
            "adoption_boost": 1.3,   # faster emerging market growth assumed
        },
    }

    f = concept_factors[data.concept]
    concept_label = f["label"]

    # ── Metric computation ────────────────────────────────────────────────────
    # All outputs are unit-less index values unless explicitly noted.
    # Coefficients are heuristic — chosen to be directionally sensible,
    # not calibrated against real-world datasets.

    # Cost pressure index (lower = more favorable cost position)
    # Anchored at 100 = pure kerosene fuel, no carbon policy, no SAF mandate.
    # SAF integration and higher hydrogen readiness reduce cost pressure.
    # Electricity price exposure and demand-driven scaling increase it.
    cost_pressure_index = round(
        100 * f["capex_pressure"]
        - data.saf_share * 0.15
        - data.hydrogen_readiness * 0.05
        + data.electricity_price * 1.2
        - data.carbon_price * 0.03
        + data.demand_growth * 0.4,
        1,
    )

    # Emissions intensity index (lower = better climate performance)
    # Anchored at 100 = pure kerosene baseline (reference: current commercial aviation).
    # SAF blending and hydrogen readiness are the primary levers.
    # Electricity price exposure is a proxy for grid carbon intensity.
    # Carbon pricing creates indirect emissions discipline.
    emissions_index = round(
        max(
            0,
            100
            - data.saf_share * 0.45
            - data.hydrogen_readiness * 0.18
            - data.carbon_price * 0.05
            + data.electricity_price * 0.25,
        ),
        1,
    )

    # Technical readiness risk index (lower = closer to deployment-ready)
    # Base risk is elevated; hydrogen readiness is the main de-risking lever.
    # Concept complexity increases base risk.
    # SAF maturity provides a modest de-risking effect.
    technical_risk_index = round(
        max(
            0,
            min(
                100,
                65
                - data.hydrogen_readiness * 0.35
                + data.demand_growth * 0.12
                + f["complexity"] * 8
                - data.saf_share * 0.05,
            ),
        ),
        1,
    )

    # Adoption potential index (higher = stronger commercial traction signal)
    # Combines SAF deployment readiness, hydrogen maturity, and market demand signals.
    # Concept-specific adoption boost/penalty applied.
    adoption_index = round(
        max(
            0,
            min(
                100,
                (
                    data.saf_share * 0.5
                    + data.hydrogen_readiness * 0.25
                    + data.demand_growth * 0.4
                )
                * f["adoption_boost"],
            ),
        ),
        1,
    )

    # Narrative strength index (higher = stronger investor-facing signal)
    # ⚠ This is a heuristic composite for discussion purposes only.
    # It is NOT a predictive metric and should not be treated as a forecast.
    # High SAF share, high carbon price, and high hydrogen readiness
    # are treated as positive narrative signals; high electricity cost is negative.
    narrative_index = round(
        max(
            0,
            min(
                100,
                45
                + data.saf_share * 0.15
                + data.hydrogen_readiness * 0.18
                - data.electricity_price * 0.4
                + data.carbon_price * 0.06
                + data.demand_growth * 0.1,
            ),
        ),
        1,
    )

    outputs = {
        "cost_pressure_index": cost_pressure_index,
        "emissions_index": emissions_index,
        "technical_risk_index": technical_risk_index,
        "adoption_index": adoption_index,
        "narrative_index": narrative_index,
    }

    # ── Benchmarks ────────────────────────────────────────────────────────────
    # Reference points are illustrative anchors for structured discussion.
    # They are NOT sourced from a single authoritative standard.
    # Each benchmark has a label, description, and directional rationale.
    benchmarks = {
        "cost_pressure_index": {
            "label": "Kerosene-only, no-policy baseline",
            "description": (
                "Index anchored at 100 = pure kerosene fuel with no SAF mandate and no carbon pricing. "
                "A scenario below 100 suggests more favorable cost positioning under these assumptions."
            ),
            "value": 100.0,
            "unit": "index (unitless)",
            "lower_is_better": True,
        },
        "emissions_index": {
            "label": "CORSIA 2035 ambition proxy (~80)",
            "description": (
                "Illustrative reference aligned with the CORSIA 2035 carbon-neutral growth ambition. "
                "Below 80 suggests the scenario is aligned with medium-term decarbonization targets. "
                "Below 50 would be roughly aligned with a Paris-compatible 2050 trajectory."
            ),
            "value": 80.0,
            "unit": "index (unitless, 100 = kerosene baseline)",
            "lower_is_better": True,
        },
        "technical_risk_index": {
            "label": "Deployment-ready threshold proxy (~30)",
            "description": (
                "Heuristic: below 30 suggests the concept is sufficiently mature for serious commercial "
                "entry discussion. Above 60 indicates significant readiness gaps that need de-risking."
            ),
            "value": 30.0,
            "unit": "index (unitless)",
            "lower_is_better": True,
        },
        "adoption_index": {
            "label": "Strong commercial traction reference (~50)",
            "description": (
                "Heuristic: above 50 suggests the assumption set is consistent with a commercially "
                "credible growth trajectory. Below 30 suggests adoption conditions are not yet mature."
            ),
            "value": 50.0,
            "unit": "index (unitless)",
            "lower_is_better": False,
        },
        "narrative_index": {
            "label": "Compelling investor-narrative reference (~65)",
            "description": (
                "Heuristic composite. Above 65 suggests the scenario supports a compelling climate-tech "
                "investment narrative. ⚠ This is not a predictive metric — use for framing only."
            ),
            "value": 65.0,
            "unit": "index (unitless, heuristic)",
            "lower_is_better": False,
        },
    }

    # ── Benchmark readings ────────────────────────────────────────────────────
    readings = {
        key: classify_gap(
            outputs[key],
            benchmarks[key]["value"],
            lower_is_better=benchmarks[key]["lower_is_better"],
        )
        for key in benchmarks
    }

    reading_labels = {k: v["label"] for k, v in readings.items()}

    # ── Comparison table ──────────────────────────────────────────────────────
    metric_display_names = {
        "cost_pressure_index": "Cost pressure index",
        "emissions_index": "Emissions intensity index",
        "technical_risk_index": "Technical readiness risk index",
        "adoption_index": "Adoption potential index",
        "narrative_index": "Narrative strength index ⚠",
    }

    comparison_table = [
        {
            "key": key,
            "metric_label": metric_display_names[key],
            "scenario_value": outputs[key],
            "unit": benchmarks[key]["unit"],
            "benchmark_value": benchmarks[key]["value"],
            "benchmark_label": benchmarks[key]["label"],
            "benchmark_description": benchmarks[key]["description"],
            "reading": readings[key]["label"],
            "gap_pct": readings[key]["gap_pct"],
            "lower_is_better": benchmarks[key]["lower_is_better"],
        }
        for key in benchmarks
    ]

    # ── Strengths and watchouts ───────────────────────────────────────────────
    # Generated dynamically from actual computed readings — not hardcoded.
    strengths = []
    watchouts = []

    if reading_labels["emissions_index"] == "Better than benchmark":
        strengths.append(
            f"Climate performance (emissions index: {emissions_index}) is below the CORSIA 2035 "
            f"proxy reference (80) — suggesting meaningful decarbonization potential under these assumptions."
        )
    if reading_labels["adoption_index"] in ["Near benchmark", "Better than benchmark"]:
        strengths.append(
            f"Adoption potential (index: {adoption_index}) is at or above the commercial traction reference (50), "
            f"indicating that demand and technology conditions are directionally supportive."
        )
    if reading_labels["cost_pressure_index"] == "Better than benchmark":
        strengths.append(
            f"Cost pressure index ({cost_pressure_index}) is below the kerosene baseline (100) — "
            f"suggesting a favorable cost position under the current assumption set."
        )
    if reading_labels["narrative_index"] in ["Near benchmark", "Better than benchmark"]:
        strengths.append(
            f"Narrative index ({narrative_index}) is at or above the reference threshold (65), "
            f"supporting a climate-tech investment framing. (Heuristic only — not a financial forecast.)"
        )

    if reading_labels["cost_pressure_index"] == "Above benchmark":
        watchouts.append(
            f"Cost pressure index ({cost_pressure_index}) exceeds the kerosene baseline reference (100). "
            f"High electricity price exposure or low SAF/hydrogen assumptions are the likely drivers. "
            f"Validate energy cost assumptions before drawing cost conclusions."
        )
    if reading_labels["technical_risk_index"] == "Above benchmark":
        watchouts.append(
            f"Technical readiness risk ({technical_risk_index}) remains elevated above the deployment-ready "
            f"threshold (30). Hydrogen integration pathway and certification timeline need clearer definition."
        )
    if reading_labels["adoption_index"] == "Below benchmark":
        watchouts.append(
            f"Adoption potential ({adoption_index}) is below the strong commercial traction reference (50). "
            f"Consider whether SAF availability, market demand, or infrastructure readiness assumptions "
            f"are sufficiently ambitious for the target timeframe."
        )

    if not strengths:
        strengths.append(
            "No clear benchmark advantages emerge at this assumption set. "
            "Adjusting SAF share, hydrogen readiness, or carbon price may shift the picture significantly."
        )
    if not watchouts:
        watchouts.append(
            "No major benchmark gaps stand out at this scenario. "
            "Assumptions still need external validation before drawing firm conclusions."
        )

    # ── Headline ──────────────────────────────────────────────────────────────
    n_better = sum(1 for r in reading_labels.values() if r == "Better than benchmark")
    n_gap = sum(1 for r in reading_labels.values() if r in ["Above benchmark", "Below benchmark"])

    if reading_labels["cost_pressure_index"] == "Above benchmark" and reading_labels["technical_risk_index"] == "Above benchmark":
        headline = "Promising decarbonization narrative — but cost pressure and technical readiness remain the key gating factors."
    elif reading_labels["emissions_index"] == "Better than benchmark" and reading_labels["adoption_index"] != "Below benchmark":
        headline = "Credible decarbonization case with commercially relevant traction — cost and risk position to watch."
    elif n_better >= 3:
        headline = "Scenario shows broad alignment with benchmark references — climate, cost, and traction are directionally supportive."
    elif n_gap >= 3:
        headline = "Multiple benchmark gaps visible — scenario assumptions may need revision before supporting a strong case."
    else:
        headline = "Scenario is directionally interesting with a mixed benchmark profile — key open questions remain."

    # ── Interpretation (dynamic) ──────────────────────────────────────────────
    interpretation = generate_interpretation(concept_label, reading_labels, outputs)

    # ── Response ──────────────────────────────────────────────────────────────
    return {
        "scenario_label": concept_label,
        "inputs": {
            "concept": data.concept,
            "saf_share": data.saf_share,
            "hydrogen_readiness": data.hydrogen_readiness,
            "electricity_price": data.electricity_price,
            "carbon_price": data.carbon_price,
            "demand_growth": data.demand_growth,
        },
        "outputs": outputs,
        "headline": headline,
        "interpretation": interpretation,
        "strengths": strengths,
        "watchouts": watchouts,
        "comparison_table": comparison_table,
        "methodology_note": (
            "This prototype translates scenario assumptions into indexed outputs and compares them "
            "against explicit reference benchmarks. All metrics are heuristic proxies — not calibrated "
            "engineering or financial quantities. Benchmarks are illustrative references, not official standards. "
            "Intended for structured conversation and early-stage decision support only."
        ),
        "model_caveats": [
            "All metric values are unit-less index outputs derived from heuristic coefficients, not calibrated models.",
            "Benchmarks are directionally credible but not sourced from a single authoritative standard.",
            "The narrative strength index is a heuristic composite for framing — not a predictive or validated metric.",
            "Concept modifiers (regional / narrowbody / drone) are illustrative adjustments, not certified performance data.",
            "Coefficients have not been validated against real fleet, market, or financial data.",
        ],
    }
