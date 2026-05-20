// Polaris — Drone Deployment Decision Engine v2
// All constants sourced from MODEL.md (FAA-107, FAA-108, PwC-2016, MU-EXT, BARCLAYS-2026, MANNA-2025)

export type UseCase = "inspection" | "delivery" | "agriculture";
export type Platform = "light" | "professional" | "heavy";
export type BVLOSStatus = "authorized" | "waiver_pending" | "not_authorized";
export type Geography = "urban" | "suburban" | "rural" | "remote";
export type LaborMultiplier = "low" | "standard" | "high";
export type HumanAlternative =
  | "helicopter"
  | "rope_access"
  | "ground_crew"
  | "aerial"
  | "ground";
export type Verdict = "GO" | "CONDITIONAL" | "NO-GO";

export interface ScenarioInputs {
  useCase: UseCase;
  platform: Platform;
  missionRange: number; // km one-way
  payload: number;      // kg
  bvlosStatus: BVLOSStatus;
  annualMissions: number;
  geography: Geography;
  laborMultiplier: LaborMultiplier;
  humanAlternative: HumanAlternative;
}

export interface ScenarioOutputs {
  verdict: Verdict;
  bindingConstraint: string;
  resolutionPath: string;
  droneDOC: number;
  humanCost: number;
  savingsPerMission: number;
  savingsPct: number;
  annualSavings: number;
  breakEvenVolume: number;
  paybackMonths: number;
  flightTimeHr: number;
  missionDurationHr: number;
  bvlosRequired: boolean;
  bvlosUnlockValue: number | null;
  narrative: string;
  flags: string[];
  // Economic outlook even when regulatory constraint fires
  economicViable: boolean;
}

// ── Platform constants ─────────────────────────────────────────────────────────

const PLATFORM_COST: Record<Platform, number> = {
  light: 6500,
  professional: 20000,
  heavy: 50000,
};

const PLATFORM_MAX_PAYLOAD: Record<Platform, number> = {
  light: 0.9,
  professional: 2.7,
  heavy: 5.0,
};

const PLATFORM_MAX_RANGE: Record<Platform, { vlos: number; bvlos: number }> = {
  light:        { vlos: 5,  bvlos: 10 },
  professional: { vlos: 8,  bvlos: 20 },
  heavy:        { vlos: 12, bvlos: 40 },
};

const CRUISE_SPEED: Record<Platform, number> = {
  light: 45,
  professional: 50,
  heavy: 55,
};

const BATTERY_COST: Record<Platform, number> = {
  light: 300,
  professional: 450,
  heavy: 600,
};

const INSURANCE_ANNUAL: Record<Platform, number> = {
  light: 800,
  professional: 2000,
  heavy: 4000,
};

// ── Setup time by use case ────────────────────────────────────────────────────
// Inspection / agriculture: 0.5 hr — calibration, safety check, equipment setup
// Delivery: 0.1 hr (~6 min) — pre-loaded drone, minimal pre-flight for dedicated ops
// Source: Manna / Wing operational benchmarks; inspection standard (PwC-2016)

const SETUP_TIME_HR: Record<UseCase, number> = {
  inspection: 0.5,
  delivery: 0.1,
  agriculture: 0.5,
};

// ── Labor multipliers ─────────────────────────────────────────────────────────

const LABOR_MULT: Record<LaborMultiplier, number> = {
  low: 0.7,
  standard: 1.0,
  high: 1.5,
};

// ── Human alternative costs ───────────────────────────────────────────────────
// Delivery costs updated to reflect standalone trip cost, not amortized dense-route rate.
// Dense van routes (30-50 stops/day) yield $3-8/stop — unfair comparison for drone 1:1 trips.
// These values represent the cost of a dedicated delivery to a single location per geography.
// Sources: McKinsey Last-Mile Delivery 2022; BARCLAYS-2026; DHL Rural Delivery Studies 2023.

const DELIVERY_COST: Record<Geography, number> = {
  urban:    8,   // Highly optimized van routes; drone rarely competitive here
  suburban: 15,  // Mixed density; 10-20 stops/day amortized trip cost
  rural:    35,  // Low density; each delivery is largely a dedicated trip (~3-5 stops/run)
  remote:   55,  // Individual trip required; high driver time + fuel
};

const AG_COVERAGE: Record<Platform, number> = {
  light: 8,
  professional: 13,
  heavy: 20,
};

// ── Locale-independent number formatter ───────────────────────────────────────

function fmtUSD(n: number): string {
  const rounded = Math.round(Math.abs(n)).toString();
  return "$" + rounded.replace(/\B(?=(\d{3})+(?!\d))/g, ",");
}

// ── Main computation ──────────────────────────────────────────────────────────

export function runEngine(inputs: ScenarioInputs): ScenarioOutputs {
  const {
    useCase,
    platform,
    missionRange,
    payload,
    bvlosStatus,
    annualMissions,
    geography,
    laborMultiplier,
    humanAlternative,
  } = inputs;

  const laborMult = LABOR_MULT[laborMultiplier];
  const flags: string[] = [];
  let bindingConstraint = "";
  let resolutionPath = "";
  let verdict: Verdict = "GO";

  // ── BVLOS requirement ────────────────────────────────────────────────────────
  // Agriculture: operator stands at field edge — BVLOS never required.
  // missionRange is reinterpreted as field acres for agriculture, not transit distance.
  const bvlosRequired = useCase !== "agriculture" && missionRange > 1.5;
  const effectiveMaxRange = bvlosRequired
    ? PLATFORM_MAX_RANGE[platform].bvlos
    : PLATFORM_MAX_RANGE[platform].vlos;

  // ── Hard constraint checks (priority order) ──────────────────────────────────

  // 1. Payload
  if (payload > PLATFORM_MAX_PAYLOAD[platform]) {
    verdict = "NO-GO";
    bindingConstraint = `Payload (${payload} kg) exceeds platform capacity (${PLATFORM_MAX_PAYLOAD[platform]} kg max for ${platform} tier)`;
    resolutionPath = "Upgrade to a heavier platform tier, or reduce sensor payload weight.";
  }

  // 2. Range / endurance (not applicable to agriculture — missionRange = field acres there)
  if (!bindingConstraint && useCase !== "agriculture" && missionRange > effectiveMaxRange) {
    verdict = "NO-GO";
    bindingConstraint = `Mission range (${missionRange} km) exceeds platform endurance (${effectiveMaxRange} km ${bvlosRequired ? "BVLOS" : "VLOS"} for ${platform} tier)`;
    resolutionPath = "Upgrade platform tier, or deploy an intermediate relay / recharge station.";
  }

  // 3a. BVLOS not authorized → hard NO-GO
  if (!bindingConstraint && bvlosRequired && bvlosStatus === "not_authorized") {
    verdict = "NO-GO";
    bindingConstraint = "BVLOS required but not authorized";
    resolutionPath =
      "Obtain a Part 107 §107.31 waiver (90-day FAA process), or await the Part 108 permit framework (expected 2026–27). [FAA-108]";
  }

  // 3b. BVLOS waiver pending → CONDITIONAL (deployment blocked, not impossible)
  if (!bindingConstraint && bvlosRequired && bvlosStatus === "waiver_pending") {
    verdict = "CONDITIONAL";
    bindingConstraint = "BVLOS waiver pending — deployment blocked until FAA approval";
    resolutionPath = "Awaiting FAA review. Standard Part 107 §107.31 waiver review: ~90 days. [FAA-107]";
  }

  // Urban delivery flag
  if (geography === "urban" && useCase === "delivery") {
    flags.push("Urban airspace: LAANC authorization required before each flight. [FAA-107 §107.41]");
  }

  // Platform mismatch flag for delivery
  if (useCase === "delivery" && platform !== "light") {
    flags.push(
      `Platform note: ${platform === "professional" ? "Professional ($20k Matrice-class)" : "Heavy ($50k)"} platforms are rarely used for package delivery. Light-tier drones ($6.5k, 0.9 kg payload) are the standard for last-mile ops and significantly reduce per-mission cost.`
    );
  }

  // ── Flight time ───────────────────────────────────────────────────────────────
  let flightTimeHr: number;
  let missionDurationHr: number;

  if (useCase === "inspection" && humanAlternative === "rope_access") {
    // Point-asset inspection: on-site hover, not linear distance
    flightTimeHr = 0.5;
    missionDurationHr = flightTimeHr + SETUP_TIME_HR.inspection;
  } else if (useCase === "agriculture") {
    // missionRange is reinterpreted as field acres for agriculture.
    // Flight time = acres to cover ÷ platform coverage rate (acres/hr).
    // Operator stays at field edge — no transit distance modeled here.
    const fieldAcres = missionRange;
    flightTimeHr = fieldAcres / AG_COVERAGE[platform];
    missionDurationHr = flightTimeHr + SETUP_TIME_HR.agriculture;
  } else {
    flightTimeHr = (missionRange * 2) / CRUISE_SPEED[platform];
    missionDurationHr = flightTimeHr + SETUP_TIME_HR[useCase];
  }

  // ── Drone DOC per mission ─────────────────────────────────────────────────────
  const platformCost = PLATFORM_COST[platform];
  const depreciation = platformCost / (3 * annualMissions);
  const battery = BATTERY_COST[platform] / 250;
  const pilot = 65 * missionDurationHr;
  const maintenance = (platformCost * 0.15) / annualMissions;
  const insurance = INSURANCE_ANNUAL[platform] / annualMissions;
  const droneDOC = depreciation + battery + pilot + maintenance + insurance;

  // ── Human alternative cost ────────────────────────────────────────────────────
  let humanCost = 0;

  if (useCase === "inspection") {
    if (humanAlternative === "helicopter") {
      // Per-segment variable cost: pure flight time × hourly rate.
      // Helicopters mobilize once per day/route, not per inspection segment —
      // adding a per-mission mobilization overhead inflates cost and overstates savings.
      // Rate: $2,500/hr — consistent with National Grid ($2,500/hr for pylon inspection,
      // ~16 pylons/hr at 300m spacing ≈ $520/km effective). [NATIONAL-GRID-2023]
      // At 5km one-way (10km corridor): $417 → drone ~$106 → 75% savings (PwC: 70-80%). ✓
      const coverageKm = missionRange * 2;
      const heliTime = coverageKm / 60; // flight time only — no per-mission mobilization overhead
      humanCost = 2500 * heliTime * laborMult;
    } else if (humanAlternative === "rope_access") {
      humanCost = 4000 * laborMult;
    } else {
      // ground_crew
      const coverageKm = missionRange * 2;
      const groundTime = coverageKm / 2.5 + 0.5;
      humanCost = 150 * groundTime * laborMult;
    }
  } else if (useCase === "delivery") {
    humanCost = DELIVERY_COST[geography] * laborMult;
  } else {
    // agriculture — missionRange is field acres per mission
    const fieldAcres = missionRange;
    const agRef = humanAlternative === "aerial" ? 15 : 6;
    humanCost = agRef * fieldAcres * laborMult;
  }

  // ── Economics (always computed, regardless of regulatory constraint) ──────────
  const savingsPerMission = humanCost - droneDOC;
  const savingsPct = humanCost > 0 ? (savingsPerMission / humanCost) * 100 : 0;
  const annualSavings = savingsPerMission * annualMissions;
  const economicViable = savingsPerMission > 0;

  // ── Break-even: volume-independent, uses variable costs only ─────────────────
  // Per-mission variable costs: battery + pilot (scale with each mission flown)
  // Fixed annual costs: depreciation, maintenance, insurance (run regardless of volume)
  // Break-even = "how many missions to recoup platform cost via variable savings"
  // Using full DOC causes a circular dependency: more missions → lower DOC → different savings
  // → different break-even. This is mathematically inconsistent. Variable-only is correct.
  const variableCostPerMission = battery + pilot;
  const contributionMargin = humanCost - variableCostPerMission;

  let breakEvenVolume = 0;
  let paybackMonths = 0;
  if (contributionMargin > 0) {
    breakEvenVolume = Math.ceil(platformCost / contributionMargin);
    // Payback correctly scales with annual mission rate
    paybackMonths = (breakEvenVolume / annualMissions) * 12;
  }

  // ── CRITICAL: Warn if regulatory constraint fires but economics are also bad ──
  // This prevents the confusing "CONDITIONAL → NO-GO when I fix the regulatory issue" UX.
  if (bindingConstraint && !economicViable) {
    flags.push(
      `Economic outlook: even if this regulatory constraint is resolved, the drone (${fmtUSD(droneDOC)}/mission) would cost more than the human alternative (${fmtUSD(humanCost)}/mission) at current parameters. Fixing the regulatory issue alone won't make this viable.`
    );
  }

  // Delivery pilot overhead note — explains why delivery is hard for manually-operated drones
  if (useCase === "delivery" && !economicViable) {
    const pilotCost = pilot;
    const pilotShare = pilotCost / droneDOC;
    if (pilotShare > 0.4) {
      flags.push(
        `Why delivery is hard: pilot cost represents ${(pilotShare * 100).toFixed(0)}% of drone operating cost (${fmtUSD(pilotCost)}/mission). Drone delivery economics break even primarily in rural/remote areas where dedicated human trips are expensive, or at high volume (1,000+ missions/yr) that dilutes fixed costs. Autonomous operations (no per-mission pilot) would fundamentally change this picture.`
      );
    }
  }

  // ── Economic verdict checks (only run if no harder constraint already fired) ──
  if (!bindingConstraint && !economicViable) {
    verdict = "NO-GO";
    bindingConstraint = "Drone cost exceeds human alternative";
    resolutionPath =
      "Try: rural/remote geography (higher human alternative cost), increase annual missions to dilute fixed costs, or switch to a lighter/cheaper platform.";
  }

  if (
    !bindingConstraint &&
    contributionMargin > 0 &&
    annualMissions < breakEvenVolume * 0.5
  ) {
    verdict = "CONDITIONAL";
    bindingConstraint = `Low utilization — platform pays back in ${paybackMonths.toFixed(0)} months at current volume (${fmtUSD(annualMissions * contributionMargin - (PLATFORM_COST[platform] * 0.15 + INSURANCE_ANNUAL[platform]))}/yr net after fixed costs)`;
    resolutionPath =
      "Increase annual mission volume to dilute fixed costs, or use Drone-as-a-Service (DaaS) to avoid the platform acquisition cost entirely.";
  }

  // ── BVLOS unlock value ────────────────────────────────────────────────────────
  let bvlosUnlockValue: number | null = null;
  if (bvlosRequired && bvlosStatus !== "authorized") {
    // Guard against infinite recursion — don't recurse if already authorized
    const authorizedResult = runEngine({ ...inputs, bvlosStatus: "authorized" });
    // Only show unlock value if it's actually positive (authorized scenario is better)
    const delta = authorizedResult.annualSavings - annualSavings;
    if (delta > 0) bvlosUnlockValue = delta;
  }

  // ── Narrative ─────────────────────────────────────────────────────────────────
  const humanAltLabel: Record<HumanAlternative, string> = {
    helicopter: "manned helicopter",
    rope_access: "rope access team",
    ground_crew: "ground crew",
    aerial: "manned crop duster",
    ground: "ground sprayer",
  };

  let econOutlook = "";
  if (economicViable) {
    econOutlook = ` If resolved: ${fmtUSD(droneDOC)}/mission drone vs ${fmtUSD(humanCost)}/mission human — ${savingsPct.toFixed(1)}% saving, ${fmtUSD(annualSavings)}/yr at current volume.`;
  } else {
    econOutlook = ` Note: economics are also challenging — drone cost (${fmtUSD(droneDOC)}/mission) exceeds human alternative (${fmtUSD(humanCost)}/mission) even without the regulatory constraint.`;
  }

  let narrative = "";
  if (verdict === "GO") {
    narrative = `Deployment is viable. The drone costs ${fmtUSD(droneDOC)} per mission versus ${fmtUSD(humanCost)} for ${humanAltLabel[humanAlternative]} — a saving of ${savingsPct.toFixed(1)}%. At ${annualMissions} missions/yr, this translates to ${fmtUSD(annualSavings)} in annual savings. Platform cost recovered after ${Math.ceil(breakEvenVolume)} missions (~${paybackMonths.toFixed(1)} months).`;
  } else if (verdict === "CONDITIONAL") {
    if (bindingConstraint.includes("waiver") || bindingConstraint.includes("BVLOS")) {
      narrative = `Deployment is blocked pending regulatory approval. ${resolutionPath}${econOutlook}`;
    } else {
      narrative = `Deployment is marginally viable but held back by utilization. ${resolutionPath}${economicViable ? ` Per-mission economics are positive (${savingsPct.toFixed(1)}% saving), but the platform pays back only above ${Math.ceil(breakEvenVolume)} missions/yr.` : ""}`;
    }
  } else {
    narrative = `Deployment is not viable under current parameters. Binding constraint: ${bindingConstraint}. ${resolutionPath}`;
  }

  return {
    verdict,
    bindingConstraint,
    resolutionPath,
    droneDOC,
    humanCost,
    savingsPerMission,
    savingsPct,
    annualSavings,
    breakEvenVolume,
    paybackMonths,
    flightTimeHr,
    missionDurationHr,
    bvlosRequired,
    bvlosUnlockValue,
    narrative,
    flags,
    economicViable,
  };
}
