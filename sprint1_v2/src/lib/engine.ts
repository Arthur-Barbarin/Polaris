// Polaris — Aviation SAF Scenario Engine v1 (TypeScript port of Python backend)
// All constants sourced from IATA-CR 2024, ICAO CAEP/12 2022, CORSIA 2022, ReFuelEU 2023/2405

export type Concept = "narrowbody" | "regional" | "widebody";
export type TargetYear = 2030 | 2035 | 2050;
export type SafType = "hefa" | "ptl" | "mix";
export type TechScenario = "conservative" | "moderate" | "advanced";
export type Reading = "green" | "amber" | "red";

export interface ScenarioInputs {
  concept: Concept;
  targetYear: TargetYear;
  safSharePct: number;   // 0–100
  safType: SafType;
  techScenario: TechScenario;
}

export interface MetricRow {
  key: string;
  label: string;
  unit: string;
  scenarioValue: number;
  benchmarkValue: number;
  benchmarkLabel: string;
  reading: string;
  readingColor: Reading;
  gapPct: number | null;
  lowerIsBetter: boolean;
}

export interface ScenarioOutputs {
  // Core metrics
  co2Intensity: number;           // gCO₂/RPK
  co2ReductionPct: number;        // % from 2019
  safCostPremiumPerSeat: number;  // USD/seat
  carbonCostPerSeat: number;
  totalCostPremiumPerSeat: number;
  safBreakevenCarbonPrice: number;
  euEtsCarbonCostPerSeat: number;
  safTrl: number;                 // 1–9
  gapVsRefueleuPp: number;
  gapVsIcaoS2Pp: number;
  techDeploymentRisk: string;
  // Benchmarks for display
  bm2019: number;
  bmModerate: number;
  bmAmbitious: number;
  refueleuTarget: number;
  icaoS2Target: number;
  // Template narrative (used while Groq loads or as fallback)
  headline: string;
  interpretation: string;
  strengths: string[];
  watchouts: string[];
  // Comparison table
  comparisonTable: MetricRow[];
  // Context
  aircraftLabel: string;
  refFlight: string;
  safPrice: number;
  techNote: string;
}

// ── Physical constants ──────────────────────────────────────────────────────

const CO2_KG_PER_KG_JET_A = 3.16;       // [CAEP12] p.28
const JET_A_DENSITY_KG_PER_L = 0.804;   // ASTM D1655
const BASELINE_YEAR = 2019;
const EU_ETS_USD_PER_TCO2 = 80;
const JET_A_REF_USD_PER_TONNE = 700;

// ── Aircraft baselines ──────────────────────────────────────────────────────

const AIRCRAFT: Record<Concept, {
  label: string; co2_2019: number; fuel_l_per_rpk: number;
  ref_seats: number; ref_range_km: number;
}> = {
  narrowbody: { label: "Commercial narrowbody (A320 / B737-family)", co2_2019: 88,  fuel_l_per_rpk: 0.0347, ref_seats: 165, ref_range_km: 800   },
  regional:   { label: "Regional aircraft (ATR-72 / E175-class)",     co2_2019: 110, fuel_l_per_rpk: 0.0433, ref_seats: 75,  ref_range_km: 500   },
  widebody:   { label: "Long-haul widebody (A350 / B787-class)",      co2_2019: 72,  fuel_l_per_rpk: 0.0283, ref_seats: 280, ref_range_km: 8_000 },
};

// ── SAF pathways ────────────────────────────────────────────────────────────

const SAF_TYPES: Record<SafType, {
  label: string; lca_saving: number; trl: number;
  price: Record<number, number>;
}> = {
  hefa: { label: "Bio-SAF — HEFA",             lca_saving: 0.75, trl: 9, price: { 2030: 1100, 2035: 900,  2050: 750  } },
  ptl:  { label: "Power-to-Liquid (e-fuel)",    lca_saving: 0.90, trl: 6, price: { 2030: 2500, 2035: 1800, 2050: 1100 } },
  mix:  { label: "Mixed blend — Bio-SAF + PtL", lca_saving: 0.82, trl: 8, price: { 2030: 1700, 2035: 1300, 2050: 950  } },
};

// ── Technology efficiency scenarios ─────────────────────────────────────────

const TECH_SCENARIOS: Record<TechScenario, { label: string; annual_pct: number }> = {
  conservative: { label: "Conservative — 0.9%/yr",  annual_pct: 0.9 },
  moderate:     { label: "Moderate — 1.3%/yr",      annual_pct: 1.3 },
  advanced:     { label: "Advanced — 2.0%/yr",      annual_pct: 2.0 },
};

// ── CO₂ intensity benchmarks ────────────────────────────────────────────────

const CO2_BENCHMARKS: Record<number, { moderate: number; ambitious: number }> = {
  2030: { moderate: 74, ambitious: 65 },
  2035: { moderate: 55, ambitious: 42 },
  2050: { moderate: 22, ambitious:  8 },
};

// ── SAF mandate targets ─────────────────────────────────────────────────────

const SAF_MANDATE: Record<string, Record<number, number>> = {
  refueleu: { 2030: 6,  2035: 20, 2050: 70 },
  icao_s2:  { 2030: 13, 2035: 32, 2050: 72 },
  icao_s3:  { 2030: 21, 2035: 50, 2050: 98 },
};

// ── Helpers ─────────────────────────────────────────────────────────────────

function readingColor(reading: string): Reading {
  const green = new Set([
    "Better than benchmark", "Meets or exceeds ReFuelEU mandate",
    "Commercially available", "Cost-competitive under EU ETS",
  ]);
  const amber = new Set([
    "Near benchmark", "Near ReFuelEU mandate (within 5pp)",
    "Near cost parity", "Near commercial readiness",
  ]);
  if (green.has(reading)) return "green";
  if (amber.has(reading)) return "amber";
  return "red";
}

// ── Main engine ─────────────────────────────────────────────────────────────

export function runEngine(inputs: ScenarioInputs): ScenarioOutputs {
  const { concept, targetYear, safSharePct, safType, techScenario } = inputs;

  const ac   = AIRCRAFT[concept];
  const saf  = SAF_TYPES[safType];
  const tech = TECH_SCENARIOS[techScenario];
  const years = targetYear - BASELINE_YEAR;

  const bm = CO2_BENCHMARKS[targetYear];
  const refueleuTarget = SAF_MANDATE.refueleu[targetYear];
  const icaoS2Target   = SAF_MANDATE.icao_s2[targetYear];
  const icaoS3Target   = SAF_MANDATE.icao_s3[targetYear];

  // ── METRIC 1: CO₂ intensity ───────────────────────────────────────────────
  const techFactor = Math.pow(1 - tech.annual_pct / 100, years);
  const safFactor  = 1 - (safSharePct / 100) * saf.lca_saving;
  const co2Intensity = Math.round(ac.co2_2019 * techFactor * safFactor * 10) / 10;
  const co2ReductionPct = Math.round((1 - co2Intensity / ac.co2_2019) * 1000) / 10;

  // ── METRIC 2: SAF cost per seat ───────────────────────────────────────────
  const safPrice = saf.price[targetYear];
  const safPremiumPerTonne = Math.max(0, safPrice - JET_A_REF_USD_PER_TONNE);

  const fuelPerSeatL  = ac.fuel_l_per_rpk * ac.ref_range_km;
  const fuelPerSeatKg = fuelPerSeatL * JET_A_DENSITY_KG_PER_L;
  const fuelPerSeatT  = fuelPerSeatKg / 1000;

  const safPerSeatT    = fuelPerSeatT * (safSharePct / 100);
  const fossilPerSeatT = fuelPerSeatT * (1 - safSharePct / 100);

  const safCostPremiumPerSeat = Math.round(safPerSeatT * safPremiumPerTonne * 100) / 100;
  const fossilCo2PerSeatT     = fossilPerSeatT * CO2_KG_PER_KG_JET_A;
  const carbonCostPerSeat     = Math.round(fossilCo2PerSeatT * EU_ETS_USD_PER_TCO2 * 100) / 100;
  const totalCostPremiumPerSeat = Math.round((safCostPremiumPerSeat + carbonCostPerSeat) * 100) / 100;
  const euEtsCarbonCostPerSeat  = Math.round(fossilCo2PerSeatT * EU_ETS_USD_PER_TCO2 * 100) / 100;

  const co2SavedPerSeatT = safPerSeatT * CO2_KG_PER_KG_JET_A * saf.lca_saving;
  const safBreakevenCarbonPrice =
    co2SavedPerSeatT > 0 && safCostPremiumPerSeat > 0
      ? Math.round(safCostPremiumPerSeat / co2SavedPerSeatT)
      : 0;

  // ── METRIC 3: Policy alignment ────────────────────────────────────────────
  const gapVsRefueleuPp = Math.round((safSharePct - refueleuTarget) * 10) / 10;
  const gapVsIcaoS2Pp   = Math.round((safSharePct - icaoS2Target) * 10) / 10;

  const policyReading =
    gapVsRefueleuPp >= 0 ? "Meets or exceeds ReFuelEU mandate"
    : gapVsRefueleuPp >= -5 ? "Near ReFuelEU mandate (within 5pp)"
    : "Below ReFuelEU mandate target";

  // ── METRIC 4: SAF readiness (TRL) ─────────────────────────────────────────
  const trlBonus: Record<number, number> = { 2030: 0, 2035: 1, 2050: 2 };
  const safTrl = Math.min(9, saf.trl + trlBonus[targetYear]);

  const trlReading =
    safTrl === 9 ? "Commercially available"
    : safTrl >= 7 ? "Near commercial readiness"
    : "Development-stage — commercial scale unproven";

  // ── Tech deployment risk ──────────────────────────────────────────────────
  let techDeploymentRisk: string;
  let techNote: string;
  if (techScenario === "advanced" && targetYear <= 2035) {
    techDeploymentRisk = "High";
    techNote = `Advanced efficiency (2.0%/yr) for ${targetYear} requires step-change aircraft not yet certified. Most roadmaps assume these enter service from 2035+. [IATA-CR 2024]`;
  } else if (techScenario === "advanced") {
    techDeploymentRisk = "Medium";
    techNote = `Advanced efficiency is plausible by 2050 with sustained R&D — consistent with ICCT Breakthrough and MPP PRU/ORE roadmaps. [IATA-CR 2024]`;
  } else if (techScenario === "moderate") {
    techDeploymentRisk = "Low–Medium";
    techNote = `Moderate scenario relies on in-development aircraft and ATM improvements — well-supported by existing commitments. [CAEP12 2022]`;
  } else {
    techDeploymentRisk = "Low";
    techNote = `Conservative scenario relies only on currently certified or production-committed aircraft. Zero technology deployment risk. [CAEP12 2022]`;
  }

  // ── CO₂ benchmark comparison ──────────────────────────────────────────────
  const co2Reading =
    co2Intensity <= bm.moderate ? "Better than benchmark"
    : co2Intensity <= bm.moderate * 1.10 ? "Near benchmark"
    : "Above benchmark";

  const costReading =
    safCostPremiumPerSeat <= euEtsCarbonCostPerSeat ? "Cost-competitive under EU ETS"
    : safCostPremiumPerSeat <= euEtsCarbonCostPerSeat * 1.10 ? "Near cost parity"
    : "Premium above EU ETS equivalent";

  // ── Comparison table ──────────────────────────────────────────────────────
  const comparisonTable: MetricRow[] = [
    {
      key: "co2",
      label: "CO₂ emissions intensity",
      unit: "gCO₂/RPK",
      scenarioValue: co2Intensity,
      benchmarkValue: bm.moderate,
      benchmarkLabel: `Moderate ${targetYear} pathway (${bm.moderate} gCO₂/RPK)`,
      reading: co2Reading,
      readingColor: readingColor(co2Reading),
      gapPct: Math.round((co2Intensity - bm.moderate) / bm.moderate * 1000) / 10,
      lowerIsBetter: true,
    },
    {
      key: "policy",
      label: "SAF mandate compliance",
      unit: "% SAF vs ReFuelEU",
      scenarioValue: safSharePct,
      benchmarkValue: refueleuTarget,
      benchmarkLabel: `ReFuelEU ${targetYear} mandate (${refueleuTarget}%)`,
      reading: policyReading,
      readingColor: readingColor(policyReading),
      gapPct: gapVsRefueleuPp,
      lowerIsBetter: false,
    },
    {
      key: "cost",
      label: "SAF cost premium / seat",
      unit: `USD/seat (${ac.ref_range_km.toLocaleString()} km ref flight)`,
      scenarioValue: safCostPremiumPerSeat,
      benchmarkValue: euEtsCarbonCostPerSeat,
      benchmarkLabel: `EU ETS carbon equiv. ($${euEtsCarbonCostPerSeat.toFixed(2)}/seat)`,
      reading: costReading,
      readingColor: readingColor(costReading),
      gapPct: euEtsCarbonCostPerSeat > 0
        ? Math.round((safCostPremiumPerSeat - euEtsCarbonCostPerSeat) / euEtsCarbonCostPerSeat * 1000) / 10
        : null,
      lowerIsBetter: true,
    },
    {
      key: "trl",
      label: "SAF pathway readiness",
      unit: "TRL (1–9)",
      scenarioValue: safTrl,
      benchmarkValue: 9,
      benchmarkLabel: "Commercially deployed (TRL 9)",
      reading: trlReading,
      readingColor: readingColor(trlReading),
      gapPct: null,
      lowerIsBetter: false,
    },
  ];

  // ── Template narrative ────────────────────────────────────────────────────
  const co2Ok     = co2Intensity <= bm.moderate;
  const policyOk  = gapVsRefueleuPp >= 0;
  const costTight = safCostPremiumPerSeat > euEtsCarbonCostPerSeat && safCostPremiumPerSeat > 0.5;

  let headline: string;
  if (co2Ok && policyOk && !costTight) {
    headline = `Scenario meets ${targetYear} climate and regulatory benchmarks with SAF cost broadly offset under EU carbon pricing.`;
  } else if (co2Ok && policyOk && costTight) {
    headline = `Strong climate and compliance alignment for ${targetYear} — SAF cost premium ($${safCostPremiumPerSeat.toFixed(2)}/seat) exceeds EU ETS equivalent; breakeven at ~$${safBreakevenCarbonPrice}/tCO₂.`;
  } else if (co2Ok && !policyOk) {
    headline = `CO₂ intensity meets the ${targetYear} moderate benchmark, but SAF share (${safSharePct}%) falls ${Math.abs(gapVsRefueleuPp)}pp short of the ReFuelEU mandate.`;
  } else if (!co2Ok && policyOk) {
    headline = `SAF mandate target met for ${targetYear}, but CO₂ intensity (${co2Intensity} gCO₂/RPK) remains above the moderate benchmark (${bm.moderate} gCO₂/RPK).`;
  } else {
    headline = `Both CO₂ intensity and SAF mandate compliance show gaps against ${targetYear} benchmarks.`;
  }

  const interpretation = `For ${ac.label}: this scenario reaches ${co2Intensity} gCO₂/RPK by ${targetYear} — a ${co2ReductionPct}% reduction from the 2019 baseline (${ac.co2_2019} gCO₂/RPK). The moderate roadmap benchmark is ${bm.moderate} gCO₂/RPK. On a ${ac.ref_range_km.toLocaleString()}-km reference flight, the SAF cost premium is $${safCostPremiumPerSeat.toFixed(2)}/seat, with a carbon price breakeven of ~$${safBreakevenCarbonPrice}/tCO₂ (EU ETS today: ~$80/tCO₂).`;

  const strengths: string[] = [];
  if (co2Intensity <= bm.moderate) {
    strengths.push(`CO₂ intensity (${co2Intensity} gCO₂/RPK) meets the moderate ${targetYear} roadmap benchmark (${bm.moderate} gCO₂/RPK) — a ${co2ReductionPct}% reduction from 2019.${co2Intensity <= bm.ambitious ? ` Also below the ambitious benchmark (${bm.ambitious} gCO₂/RPK).` : ""}`);
  }
  if (gapVsRefueleuPp >= 0) {
    strengths.push(`SAF share (${safSharePct}%) meets the ReFuelEU ${targetYear} mandate (${refueleuTarget}%), required for all EU-departing flights. [EU 2023/2405]`);
  }
  if (safCostPremiumPerSeat <= euEtsCarbonCostPerSeat && euEtsCarbonCostPerSeat > 0) {
    strengths.push(`SAF cost premium ($${safCostPremiumPerSeat.toFixed(2)}/seat) is offset by the avoided carbon cost ($${euEtsCarbonCostPerSeat.toFixed(2)}/seat) under EU ETS pricing — cost-competitive today.`);
  }
  if (safTrl >= 8) {
    strengths.push(`${saf.label} is at TRL ${safTrl} — commercially available or near-ready. Supply chain risk is low. [CORSIA 2022]`);
  }
  if (strengths.length === 0) {
    strengths.push("No benchmark outperformance at this assumption set. Increasing SAF share, switching to a higher-saving pathway, or selecting a more advanced technology scenario would improve the profile.");
  }

  const watchouts: string[] = [];
  if (co2Intensity > bm.moderate) {
    watchouts.push(`CO₂ intensity (${co2Intensity} gCO₂/RPK) exceeds the moderate ${targetYear} benchmark (${bm.moderate} gCO₂/RPK). Increasing SAF share or switching to PtL would close this gap.`);
  }
  if (gapVsRefueleuPp < 0) {
    watchouts.push(`SAF share (${safSharePct}%) is ${Math.abs(gapVsRefueleuPp)}pp below the ReFuelEU ${targetYear} mandate (${refueleuTarget}%) — regulatory non-compliance for EU-market operations.`);
  }
  if (safCostPremiumPerSeat > euEtsCarbonCostPerSeat && safCostPremiumPerSeat > 0.5) {
    const netGap = Math.round((safCostPremiumPerSeat - euEtsCarbonCostPerSeat) * 100) / 100;
    watchouts.push(`SAF cost premium ($${safCostPremiumPerSeat.toFixed(2)}/seat) exceeds the EU ETS carbon equivalent ($${euEtsCarbonCostPerSeat.toFixed(2)}/seat) by $${netGap}/seat. Breakeven carbon price: ~$${safBreakevenCarbonPrice}/tCO₂.`);
  }
  if (safTrl < 8) {
    watchouts.push(`${saf.label} is at TRL ${safTrl} — commercial-scale deployment not yet proven. Supply ramp-up risk is significant for a ${targetYear} target.`);
  }
  if (techScenario === "advanced" && targetYear <= 2035) {
    watchouts.push(techNote);
  }
  if (watchouts.length === 0) {
    watchouts.push("No major benchmark gaps at this assumption set. Assumptions still require external validation before drawing firm conclusions.");
  }

  return {
    co2Intensity,
    co2ReductionPct,
    safCostPremiumPerSeat,
    carbonCostPerSeat,
    totalCostPremiumPerSeat,
    safBreakevenCarbonPrice,
    euEtsCarbonCostPerSeat,
    safTrl,
    gapVsRefueleuPp,
    gapVsIcaoS2Pp,
    techDeploymentRisk,
    bm2019: ac.co2_2019,
    bmModerate: bm.moderate,
    bmAmbitious: bm.ambitious,
    refueleuTarget,
    icaoS2Target,
    headline,
    interpretation,
    strengths,
    watchouts,
    comparisonTable,
    aircraftLabel: ac.label,
    refFlight: `${ac.ref_seats} seats × ${ac.ref_range_km.toLocaleString()} km`,
    safPrice,
    techNote,
  };
}
