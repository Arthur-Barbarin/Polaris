from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel


app = FastAPI(title="Polaris API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ScenarioInput(BaseModel):
    concept: str
    saf_share: float
    hydrogen_readiness: float
    electricity_price: float
    carbon_price: float
    demand_growth: float


@app.get("/")
def root():
    return {"message": "Polaris API is running"}


def classify_gap_ratio(value: float, benchmark: float, lower_is_better: bool) -> str:
    """
    Compare a scenario value to a benchmark and return a qualitative reading.
    """
    if benchmark == 0:
        return "No benchmark available"

    ratio = value / benchmark

    if lower_is_better:
        if ratio <= 0.9:
            return "Better than benchmark"
        if ratio <= 1.1:
            return "Near benchmark"
        return "Above benchmark"
    else:
        if ratio >= 1.1:
            return "Better than benchmark"
        if ratio >= 0.9:
            return "Near benchmark"
        return "Below benchmark"


@app.post("/run-scenario")
def run_scenario(data: ScenarioInput):
    """
    Illustrative scenario engine.

    This is not a certified engineering model.
    It is a structured assumption-to-implication prototype:
    user assumptions -> quantified outputs -> benchmark comparison -> interpretation
    """

    concept_factors = {
        "regional": {"capex": 1.0, "complexity": 1.0, "adoption": 1.0},
        "narrowbody": {"capex": 1.1, "complexity": 1.2, "adoption": 0.9},
        "drone": {"capex": 0.75, "complexity": 0.8, "adoption": 1.3},
    }

    concept_labels = {
        "regional": "Regional aircraft",
        "narrowbody": "Low-emission narrowbody",
        "drone": "Advanced air mobility / drone",
    }

    factors = concept_factors.get(data.concept, concept_factors["regional"])

    adoption = (
        data.saf_share * 0.5
        + data.hydrogen_readiness * 0.25
        + data.demand_growth * 0.4
    ) * factors["adoption"]

    unit_cost = (
        100 * factors["capex"]
        - data.saf_share * 0.15
        - data.hydrogen_readiness * 0.05
        + data.electricity_price * 1.2
        - data.carbon_price * 0.03
        + data.demand_growth * 0.4
    )

    emissions = (
        100
        - data.saf_share * 0.45
        - data.hydrogen_readiness * 0.18
        - data.carbon_price * 0.05
        + data.electricity_price * 0.25
    )

    technical_risk = (
        65
        - data.hydrogen_readiness * 0.35
        + data.demand_growth * 0.12
        + factors["complexity"] * 8
        - data.saf_share * 0.05
    )

    investor_score = (
        45
        + data.saf_share * 0.15
        + data.hydrogen_readiness * 0.18
        - data.electricity_price * 0.4
        + data.carbon_price * 0.06
        + data.demand_growth * 0.1
    )

    adoption = max(0, min(100, round(adoption, 1)))
    emissions = max(0, round(emissions, 1))
    technical_risk = max(0, min(100, round(technical_risk, 1)))
    investor_score = max(0, min(100, round(investor_score, 1)))
    unit_cost = round(unit_cost, 1)

    # Benchmarks / anchors
    # These are intentionally framed as baseline reference values for the prototype.
    benchmarks = {
        "unit_cost": {
            "label": "Baseline cost index",
            "value": 100.0,
            "unit": "index",
            "lower_is_better": True,
        },
        "emissions": {
            "label": "Current aviation baseline",
            "value": 88.0,
            "unit": "proxy index",
            "lower_is_better": True,
        },
        "technical_risk": {
            "label": "Deployment-ready risk threshold",
            "value": 30.0,
            "unit": "risk index",
            "lower_is_better": True,
        },
        "adoption": {
            "label": "Strong commercial traction reference",
            "value": 50.0,
            "unit": "%",
            "lower_is_better": False,
        },
        "investor_score": {
            "label": "Strong investor narrative reference",
            "value": 65.0,
            "unit": "index",
            "lower_is_better": False,
        },
    }

    readings = {
        "unit_cost": classify_gap_ratio(
            unit_cost,
            benchmarks["unit_cost"]["value"],
            lower_is_better=True,
        ),
        "emissions": classify_gap_ratio(
            emissions,
            benchmarks["emissions"]["value"],
            lower_is_better=True,
        ),
        "technical_risk": classify_gap_ratio(
            technical_risk,
            benchmarks["technical_risk"]["value"],
            lower_is_better=True,
        ),
        "adoption": classify_gap_ratio(
            adoption,
            benchmarks["adoption"]["value"],
            lower_is_better=False,
        ),
        "investor_score": classify_gap_ratio(
            investor_score,
            benchmarks["investor_score"]["value"],
            lower_is_better=False,
        ),
    }

    comparison_table = [
        {
            "metric": "Unit cost index",
            "scenario_value": unit_cost,
            "scenario_unit": "index",
            "benchmark_value": benchmarks["unit_cost"]["value"],
            "benchmark_unit": benchmarks["unit_cost"]["unit"],
            "benchmark_label": benchmarks["unit_cost"]["label"],
            "reading": readings["unit_cost"],
        },
        {
            "metric": "Emissions intensity proxy",
            "scenario_value": emissions,
            "scenario_unit": "index",
            "benchmark_value": benchmarks["emissions"]["value"],
            "benchmark_unit": benchmarks["emissions"]["unit"],
            "benchmark_label": benchmarks["emissions"]["label"],
            "reading": readings["emissions"],
        },
        {
            "metric": "Technical risk proxy",
            "scenario_value": technical_risk,
            "scenario_unit": "index",
            "benchmark_value": benchmarks["technical_risk"]["value"],
            "benchmark_unit": benchmarks["technical_risk"]["unit"],
            "benchmark_label": benchmarks["technical_risk"]["label"],
            "reading": readings["technical_risk"],
        },
        {
            "metric": "Adoption potential",
            "scenario_value": adoption,
            "scenario_unit": "%",
            "benchmark_value": benchmarks["adoption"]["value"],
            "benchmark_unit": benchmarks["adoption"]["unit"],
            "benchmark_label": benchmarks["adoption"]["label"],
            "reading": readings["adoption"],
        },
        {
            "metric": "Investor narrative strength",
            "scenario_value": investor_score,
            "scenario_unit": "index",
            "benchmark_value": benchmarks["investor_score"]["value"],
            "benchmark_unit": benchmarks["investor_score"]["unit"],
            "benchmark_label": benchmarks["investor_score"]["label"],
            "reading": readings["investor_score"],
        },
    ]

    strengths = []
    watchouts = []

    if readings["emissions"] == "Better than benchmark":
        strengths.append("Climate performance is stronger than the current aviation reference.")
    if readings["adoption"] in ["Near benchmark", "Better than benchmark"]:
        strengths.append("Commercial traction assumptions are directionally supportive.")
    if readings["investor_score"] in ["Near benchmark", "Better than benchmark"]:
        strengths.append("The scenario supports a reasonably strong investor-facing narrative.")

    if readings["unit_cost"] == "Above benchmark":
        watchouts.append("Cost assumptions remain above the baseline reference.")
    if readings["technical_risk"] == "Above benchmark":
        watchouts.append("Technical risk remains elevated relative to a deployment-oriented threshold.")
    if readings["adoption"] == "Below benchmark":
        watchouts.append("Adoption potential remains below a strong commercial traction reference.")

    if not strengths:
        strengths.append("The scenario creates a structured basis for discussion, but clear advantages are not yet dominant.")

    if not watchouts:
        watchouts.append("No major red flags stand out against the selected benchmark set, but assumptions still need validation.")

    if readings["unit_cost"] == "Above benchmark" and readings["technical_risk"] == "Above benchmark":
        headline = "Promising narrative, but cost and readiness remain the key gating factors."
    elif readings["emissions"] == "Better than benchmark" and readings["adoption"] != "Below benchmark":
        headline = "The scenario shows a credible decarbonization case with commercially relevant traction."
    else:
        headline = "The scenario is directionally interesting, but benchmark gaps still shape the investment case."

    interpretation = (
        f"For the selected {concept_labels.get(data.concept, 'concept')}, "
        f"the main positive signal comes from climate and market narrative potential, "
        f"while the main challenge remains cost and technical readiness."
    )

    methodology_note = (
        "This prototype translates scenario assumptions into indexed outputs and compares them "
        "against explicit reference benchmarks. It is intended for structured discussion, "
        "not as a certified engineering or financial forecast."
    )

    return {
        "scenario_label": concept_labels.get(data.concept, "Concept"),
        "inputs": {
            "concept": data.concept,
            "saf_share": data.saf_share,
            "hydrogen_readiness": data.hydrogen_readiness,
            "electricity_price": data.electricity_price,
            "carbon_price": data.carbon_price,
            "demand_growth": data.demand_growth,
        },
        "outputs": {
            "adoption": adoption,
            "unit_cost": unit_cost,
            "emissions": emissions,
            "technical_risk": technical_risk,
            "investor_score": investor_score,
        },
        "headline": headline,
        "interpretation": interpretation,
        "strengths": strengths,
        "watchouts": watchouts,
        "comparison_table": comparison_table,
        "methodology_note": methodology_note,
    }