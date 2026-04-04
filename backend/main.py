from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI(title="Polaris API")

# Allows the frontend to talk to the backend locally
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


@app.post("/run-scenario")
def run_scenario(data: ScenarioInput):
    """
    Simple illustrative model.
    This is not meant to be a physics-grade model yet.
    It is a decision-support demo.
    """

    concept_factors = {
        "regional": {"capex": 1.0, "complexity": 1.0, "adoption": 1.0},
        "narrowbody": {"capex": 1.1, "complexity": 1.2, "adoption": 0.9},
        "drone": {"capex": 0.75, "complexity": 0.8, "adoption": 1.3},
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
    viability_score = (
        100
        - unit_cost * 0.3
        - technical_risk * 0.25
        + investor_score * 0.35
        - emissions * 0.05
    )

    viability_score = max(0, min(100, round(viability_score, 1)))
    adoption = max(0, min(100, round(adoption, 1)))
    emissions = max(0, round(emissions, 1))
    technical_risk = max(0, min(100, round(technical_risk, 1)))
    investor_score = max(0, min(100, round(investor_score, 1)))
    unit_cost = round(unit_cost, 1)

    if viability_score >= 65:
        recommendation = "Promising near-term positioning"
    elif viability_score >= 50:
        recommendation = "Worth refining with sharper assumptions"
    else:
        recommendation = "Narrative is fragile — revisit concept and assumptions"

    if viability_score >= 65:
        executive_summary = (
            "This concept produces a credible early-stage story with a useful balance "
            "between adoption potential, investor appeal, and manageable technical risk."
        )
    elif viability_score >= 50:
        executive_summary = (
            "The concept has potential, but the story depends heavily on assumptions. "
            "A deeper trade study would be the next logical step."
        )
    else:
        executive_summary = (
            "The current scenario is visually compelling but strategically weak. "
            "The client should revisit technology timing, cost exposure, or market focus."
        )

    return {
        "viability_score": viability_score,
        "adoption": adoption,
        "unit_cost": unit_cost,
        "emissions": emissions,
        "technical_risk": technical_risk,
        "investor_score": investor_score,
        "recommendation": recommendation,
        "executive_summary": executive_summary,
    }