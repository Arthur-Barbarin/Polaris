"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { runEngine, ScenarioInputs, ScenarioOutputs, Concept, TargetYear, SafType, TechScenario } from "@/lib/engine";

// ── Types ────────────────────────────────────────────────────────────────────

interface Narrative {
  headline: string;
  interpretation: string;
  strengths: string[];
  watchouts: string[];
}

// ── Default inputs ───────────────────────────────────────────────────────────

const DEFAULT_INPUTS: ScenarioInputs = {
  concept: "narrowbody",
  targetYear: 2035,
  safSharePct: 20,
  safType: "hefa",
  techScenario: "moderate",
};

// ── Small UI components ───────────────────────────────────────────────────────

function ChipGroup<T extends string | number>({
  options,
  value,
  onChange,
}: {
  options: { value: T; label: string; sub?: string }[];
  value: T;
  onChange: (v: T) => void;
}) {
  return (
    <div className="flex flex-wrap gap-2">
      {options.map((o) => (
        <button
          key={o.value}
          onClick={() => onChange(o.value)}
          className={`px-3 py-1.5 rounded-full text-sm font-medium transition-colors border ${
            value === o.value
              ? "bg-sky-600 text-white border-sky-600"
              : "bg-white text-slate-700 border-slate-200 hover:border-sky-300"
          }`}
        >
          {o.label}
          {o.sub && (
            <span className={`ml-1 text-xs ${value === o.value ? "text-sky-100" : "text-slate-400"}`}>
              {o.sub}
            </span>
          )}
        </button>
      ))}
    </div>
  );
}

function Slider({
  label,
  hint,
  value,
  min,
  max,
  step,
  unit,
  onChange,
}: {
  label: string;
  hint?: string;
  value: number;
  min: number;
  max: number;
  step: number;
  unit: string;
  onChange: (v: number) => void;
}) {
  return (
    <div>
      <div className="flex items-baseline justify-between mb-1">
        <label className="text-sm font-medium text-slate-700">{label}</label>
        <span className="text-base font-semibold text-sky-700">
          {value}
          <span className="text-xs font-normal text-slate-500 ml-0.5">{unit}</span>
        </span>
      </div>
      {hint && <p className="text-xs text-slate-400 mb-2">{hint}</p>}
      <input
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        className="w-full h-1.5 bg-slate-200 rounded-full appearance-none cursor-pointer accent-sky-600"
      />
      <div className="flex justify-between text-xs text-slate-400 mt-1">
        <span>{min}{unit}</span>
        <span>{max}{unit}</span>
      </div>
    </div>
  );
}

function StepCard({
  number,
  title,
  children,
}: {
  number: number;
  title: string;
  children: React.ReactNode;
}) {
  return (
    <div className="bg-white border border-slate-200 rounded-2xl p-5 shadow-sm">
      <div className="flex items-center gap-3 mb-4">
        <span className="w-6 h-6 rounded-full bg-sky-600 text-white text-xs font-bold flex items-center justify-center flex-shrink-0">
          {number}
        </span>
        <h2 className="text-sm font-semibold text-slate-800 uppercase tracking-wide">{title}</h2>
      </div>
      {children}
    </div>
  );
}

function ReadingBadge({ reading }: { reading: string }) {
  const color =
    reading === "green"
      ? "bg-emerald-100 text-emerald-700"
      : reading === "amber"
      ? "bg-amber-100 text-amber-700"
      : "bg-red-100 text-red-700";
  const dot =
    reading === "green" ? "bg-emerald-500" : reading === "amber" ? "bg-amber-500" : "bg-red-500";
  return (
    <span className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-xs font-medium ${color}`}>
      <span className={`w-1.5 h-1.5 rounded-full ${dot}`} />
      {reading.charAt(0).toUpperCase() + reading.slice(1)}
    </span>
  );
}

// ── Metric tile ───────────────────────────────────────────────────────────────

function MetricTile({
  label,
  value,
  unit,
  reading,
  readingLabel,
}: {
  label: string;
  value: string;
  unit: string;
  reading: "green" | "amber" | "red";
  readingLabel: string;
}) {
  const border =
    reading === "green"
      ? "border-emerald-200"
      : reading === "amber"
      ? "border-amber-200"
      : "border-red-200";
  return (
    <div className={`bg-white border-2 ${border} rounded-xl p-4`}>
      <p className="text-xs font-medium text-slate-500 uppercase tracking-wider mb-1">{label}</p>
      <p className="text-2xl font-bold text-slate-900 leading-none">
        {value}
        <span className="text-xs font-normal text-slate-400 ml-1">{unit}</span>
      </p>
      <p className="text-xs text-slate-500 mt-1 leading-tight">{readingLabel}</p>
    </div>
  );
}

// ── CO₂ bar visualization ─────────────────────────────────────────────────────

function Co2Bar({
  baseline,
  moderate,
  ambitious,
  scenario,
}: {
  baseline: number;
  moderate: number;
  ambitious: number;
  scenario: number;
}) {
  const max = baseline * 1.05;
  const pct = (v: number) => Math.max(0, Math.min(100, (v / max) * 100));

  const scenarioPct = pct(scenario);
  const moderatePct = pct(moderate);
  const ambitiousPct = pct(ambitious);

  const scenarioColor =
    scenario <= moderate
      ? "bg-emerald-500"
      : scenario <= moderate * 1.1
      ? "bg-amber-500"
      : "bg-red-500";

  return (
    <div>
      <p className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-3">
        CO₂ intensity — scenario vs benchmarks
      </p>
      <div className="space-y-2.5">
        {/* Baseline */}
        <div className="flex items-center gap-2">
          <span className="text-xs text-slate-400 w-20 text-right flex-shrink-0">2019 base</span>
          <div className="flex-1 bg-slate-100 rounded-full h-3 relative">
            <div className="absolute left-0 top-0 h-3 w-full bg-slate-300 rounded-full" />
          </div>
          <span className="text-xs font-medium text-slate-600 w-14">{baseline} g</span>
        </div>
        {/* Scenario */}
        <div className="flex items-center gap-2">
          <span className="text-xs text-slate-700 font-semibold w-20 text-right flex-shrink-0">
            Scenario
          </span>
          <div className="flex-1 bg-slate-100 rounded-full h-3 relative">
            <div
              className={`absolute left-0 top-0 h-3 rounded-full transition-all duration-500 ${scenarioColor}`}
              style={{ width: `${scenarioPct}%` }}
            />
          </div>
          <span className="text-xs font-bold text-slate-900 w-14">{scenario} g</span>
        </div>
        {/* Moderate benchmark */}
        <div className="flex items-center gap-2">
          <span className="text-xs text-slate-400 w-20 text-right flex-shrink-0">Moderate</span>
          <div className="flex-1 bg-slate-100 rounded-full h-3 relative">
            <div
              className="absolute left-0 top-0 h-3 rounded-full bg-sky-300"
              style={{ width: `${moderatePct}%` }}
            />
          </div>
          <span className="text-xs font-medium text-slate-500 w-14">{moderate} g</span>
        </div>
        {/* Ambitious benchmark */}
        <div className="flex items-center gap-2">
          <span className="text-xs text-slate-400 w-20 text-right flex-shrink-0">Ambitious</span>
          <div className="flex-1 bg-slate-100 rounded-full h-3 relative">
            <div
              className="absolute left-0 top-0 h-3 rounded-full bg-sky-500"
              style={{ width: `${ambitiousPct}%` }}
            />
          </div>
          <span className="text-xs font-medium text-slate-500 w-14">{ambitious} g</span>
        </div>
      </div>
      <p className="text-xs text-slate-400 mt-2">gCO₂/RPK · IATA-CR 2024 / ICAO CAEP/12</p>
    </div>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────

export default function Home() {
  const [inputs, setInputs] = useState<ScenarioInputs>(DEFAULT_INPUTS);
  const [result, setResult] = useState<ScenarioOutputs>(() => runEngine(DEFAULT_INPUTS));
  const [narrative, setNarrative] = useState<Narrative | null>(null);
  const [narrativeLoading, setNarrativeLoading] = useState(false);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const set = useCallback(<K extends keyof ScenarioInputs>(key: K, value: ScenarioInputs[K]) => {
    setInputs((prev) => ({ ...prev, [key]: value }));
  }, []);

  // Recompute engine synchronously on every input change
  useEffect(() => {
    const r = runEngine(inputs);
    setResult(r);

    // Reset narrative to template while debounce runs
    setNarrative({
      headline: r.headline,
      interpretation: r.interpretation,
      strengths: r.strengths,
      watchouts: r.watchouts,
    });

    // Debounced Groq call
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(async () => {
      setNarrativeLoading(true);
      try {
        const res = await fetch("/api/narrative", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ scenarioResult: r }),
        });
        if (res.ok) {
          const data = await res.json();
          setNarrative(data);
        }
      } catch {
        // Keep template narrative on error
      } finally {
        setNarrativeLoading(false);
      }
    }, 700);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [inputs]);

  const co2Row = result.comparisonTable.find((r) => r.key === "co2")!;
  const policyRow = result.comparisonTable.find((r) => r.key === "policy")!;
  const costRow = result.comparisonTable.find((r) => r.key === "cost")!;
  const trlRow = result.comparisonTable.find((r) => r.key === "trl")!;

  return (
    <div className="min-h-screen flex flex-col">
      {/* ── Nav ─────────────────────────────────────────────────────────────── */}
      <nav className="sticky top-0 z-30 bg-white/90 backdrop-blur border-b border-slate-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 h-14 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <span className="text-sm tracking-tight">
              <span className="font-bold text-slate-900">Polaris</span>
              <span className="font-light text-slate-500"> Systems</span>
            </span>
            <span className="hidden sm:inline text-xs text-slate-300">|</span>
            <span className="hidden sm:inline text-xs text-slate-400">
              Aviation SAF Scenario Explorer
            </span>
          </div>
          <div className="text-xs text-slate-400 hidden sm:block">
            Sources: IATA-CR 2024 · ICAO CAEP/12 · ReFuelEU 2023/2405
          </div>
        </div>
      </nav>

      {/* ── Hero ─────────────────────────────────────────────────────────────── */}
      <div className="bg-gradient-to-br from-slate-900 via-slate-800 to-sky-900 text-white px-4 sm:px-6 py-10 sm:py-14">
        <div className="max-w-7xl mx-auto">
          <p className="text-sky-400 text-xs font-semibold uppercase tracking-widest mb-3">
            Decision Modeling · Aviation Decarbonization
          </p>
          <h1 className="text-2xl sm:text-3xl lg:text-4xl font-bold leading-tight max-w-2xl">
            Does your SAF strategy hold up against industry benchmarks?
          </h1>
          <p className="mt-3 text-slate-300 text-sm sm:text-base max-w-xl leading-relaxed">
            Set your assumptions. Stress-test them against IATA, ICAO CAEP/12, and ReFuelEU mandates.
            See where the gaps are — and what they cost.
          </p>
        </div>
      </div>

      {/* ── Two-column layout ─────────────────────────────────────────────────── */}
      <div className="flex-1 max-w-7xl mx-auto w-full px-4 sm:px-6 py-8">
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 items-start">

          {/* ── LEFT: Form ─────────────────────────────────────────────────── */}
          <div className="space-y-4">

            {/* Step 1: Aircraft concept */}
            <StepCard number={1} title="Aircraft concept">
              <div className="space-y-3">
                {(
                  [
                    { value: "narrowbody", label: "Narrowbody", sub: "A320/B737 · 88 gCO₂/RPK" },
                    { value: "regional",   label: "Regional",   sub: "ATR-72/E175 · 110 g" },
                    { value: "widebody",   label: "Widebody",   sub: "A350/B787 · 72 g" },
                  ] as { value: Concept; label: string; sub: string }[]
                ).map((opt) => (
                  <button
                    key={opt.value}
                    onClick={() => set("concept", opt.value)}
                    className={`w-full text-left px-4 py-3 rounded-xl border transition-colors ${
                      inputs.concept === opt.value
                        ? "border-sky-500 bg-sky-50"
                        : "border-slate-200 bg-white hover:border-sky-200"
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <span className={`text-sm font-semibold ${inputs.concept === opt.value ? "text-sky-700" : "text-slate-800"}`}>
                        {opt.label}
                      </span>
                      <span className="text-xs text-slate-400">{opt.sub}</span>
                    </div>
                    <p className="text-xs text-slate-500 mt-0.5">
                      {opt.value === "narrowbody" && "Commercial narrowbody — A320 / B737-family"}
                      {opt.value === "regional"   && "Regional aircraft — ATR-72 / E175-class"}
                      {opt.value === "widebody"   && "Long-haul widebody — A350 / B787-class"}
                    </p>
                  </button>
                ))}
              </div>
            </StepCard>

            {/* Step 2: Target year */}
            <StepCard number={2} title="Target year">
              <ChipGroup<TargetYear>
                options={[
                  { value: 2030, label: "2030" },
                  { value: 2035, label: "2035" },
                  { value: 2050, label: "2050" },
                ]}
                value={inputs.targetYear}
                onChange={(v) => set("targetYear", v)}
              />
              <p className="text-xs text-slate-400 mt-2">
                Benchmarks and mandate targets update automatically for the selected horizon.
              </p>
            </StepCard>

            {/* Step 3: SAF share */}
            <StepCard number={3} title="SAF blend share">
              <Slider
                label="SAF share of total fuel"
                hint={`ReFuelEU mandate for ${inputs.targetYear}: ${result.refueleuTarget}% · ICAO S2: ${result.icaoS2Target}%`}
                value={inputs.safSharePct}
                min={0}
                max={100}
                step={1}
                unit="%"
                onChange={(v) => set("safSharePct", v)}
              />
            </StepCard>

            {/* Step 4: SAF pathway */}
            <StepCard number={4} title="SAF pathway">
              <ChipGroup
                options={[
                  { value: "hefa", label: "Bio-SAF (HEFA)", sub: "TRL 9" },
                  { value: "ptl",  label: "Power-to-Liquid", sub: "TRL 6" },
                  { value: "mix",  label: "Blended mix", sub: "TRL 8" },
                ] as { value: SafType; label: string; sub: string }[]}
                value={inputs.safType}
                onChange={(v) => set("safType", v)}
              />
              <div className="mt-3 grid grid-cols-3 gap-2 text-center">
                <div className="bg-slate-50 rounded-lg p-2">
                  <p className="text-xs text-slate-400">LCA saving</p>
                  <p className="text-sm font-semibold text-slate-700">
                    {inputs.safType === "hefa" ? "75%" : inputs.safType === "ptl" ? "90%" : "82%"}
                  </p>
                </div>
                <div className="bg-slate-50 rounded-lg p-2">
                  <p className="text-xs text-slate-400">Price {inputs.targetYear}</p>
                  <p className="text-sm font-semibold text-slate-700">
                    ${result.safPrice.toLocaleString()}/t
                  </p>
                </div>
                <div className="bg-slate-50 rounded-lg p-2">
                  <p className="text-xs text-slate-400">TRL</p>
                  <p className="text-sm font-semibold text-slate-700">{result.safTrl}/9</p>
                </div>
              </div>
            </StepCard>

            {/* Step 5: Tech scenario */}
            <StepCard number={5} title="Technology efficiency scenario">
              <ChipGroup
                options={[
                  { value: "conservative", label: "Conservative", sub: "0.9%/yr" },
                  { value: "moderate",     label: "Moderate",     sub: "1.3%/yr" },
                  { value: "advanced",     label: "Advanced",     sub: "2.0%/yr" },
                ] as { value: TechScenario; label: string; sub: string }[]}
                value={inputs.techScenario}
                onChange={(v) => set("techScenario", v)}
              />
              {result.techDeploymentRisk === "High" && (
                <div className="mt-3 flex items-start gap-2 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2">
                  <span className="text-amber-500 text-sm mt-0.5 flex-shrink-0">⚠</span>
                  <p className="text-xs text-amber-700 leading-snug">{result.techNote}</p>
                </div>
              )}
            </StepCard>
          </div>

          {/* ── RIGHT: Results (sticky on lg) ────────────────────────────────── */}
          <div className="lg:sticky lg:top-20 space-y-4">

            {/* Metric tiles */}
            <div className="grid grid-cols-2 gap-3">
              <MetricTile
                label="CO₂ intensity"
                value={result.co2Intensity.toString()}
                unit="gCO₂/RPK"
                reading={co2Row.readingColor}
                readingLabel={co2Row.reading}
              />
              <MetricTile
                label="Policy compliance"
                value={`${inputs.safSharePct}%`}
                unit={`vs ${result.refueleuTarget}% target`}
                reading={policyRow.readingColor}
                readingLabel={policyRow.reading}
              />
              <MetricTile
                label="SAF cost premium"
                value={`$${result.safCostPremiumPerSeat.toFixed(2)}`}
                unit="/ seat"
                reading={costRow.readingColor}
                readingLabel={costRow.reading}
              />
              <MetricTile
                label="Pathway readiness"
                value={`TRL ${result.safTrl}`}
                unit="/ 9"
                reading={trlRow.readingColor}
                readingLabel={trlRow.reading}
              />
            </div>

            {/* CO₂ bar chart */}
            <div className="bg-white border border-slate-200 rounded-2xl p-5 shadow-sm">
              <Co2Bar
                baseline={result.bm2019}
                moderate={result.bmModerate}
                ambitious={result.bmAmbitious}
                scenario={result.co2Intensity}
              />
            </div>

            {/* Narrative */}
            <div className="bg-white border border-slate-200 rounded-2xl p-5 shadow-sm">
              <div className="flex items-center gap-2 mb-3">
                <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                  Scenario assessment
                </h3>
                {narrativeLoading && (
                  <span className="text-xs text-slate-300 animate-pulse">Updating…</span>
                )}
              </div>

              {narrative && (
                <>
                  {/* Headline */}
                  <p className="text-sm font-semibold text-slate-800 leading-snug mb-2">
                    {narrative.headline}
                  </p>
                  {/* Interpretation */}
                  <p className="text-xs text-slate-500 leading-relaxed mb-4">
                    {narrative.interpretation}
                  </p>

                  {/* Strengths */}
                  {narrative.strengths.length > 0 && (
                    <div className="mb-3">
                      <p className="text-xs font-semibold text-emerald-700 uppercase tracking-wide mb-1.5">
                        Strengths
                      </p>
                      <ul className="space-y-1.5">
                        {narrative.strengths.map((s, i) => (
                          <li key={i} className="flex items-start gap-2">
                            <span className="text-emerald-500 mt-0.5 flex-shrink-0 text-xs">✓</span>
                            <span className="text-xs text-slate-600 leading-snug">{s}</span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}

                  {/* Watchouts */}
                  {narrative.watchouts.length > 0 && (
                    <div>
                      <p className="text-xs font-semibold text-amber-700 uppercase tracking-wide mb-1.5">
                        Watch-outs
                      </p>
                      <ul className="space-y-1.5">
                        {narrative.watchouts.map((w, i) => (
                          <li key={i} className="flex items-start gap-2">
                            <span className="text-amber-500 mt-0.5 flex-shrink-0 text-xs">△</span>
                            <span className="text-xs text-slate-600 leading-snug">{w}</span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                </>
              )}
            </div>

            {/* Comparison table */}
            <div className="bg-white border border-slate-200 rounded-2xl p-5 shadow-sm overflow-x-auto">
              <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-500 mb-3">
                Benchmark comparison
              </h3>
              <table className="w-full text-xs">
                <thead>
                  <tr className="border-b border-slate-100">
                    <th className="text-left text-slate-400 font-medium pb-2 pr-3">Metric</th>
                    <th className="text-right text-slate-400 font-medium pb-2 pr-3">Scenario</th>
                    <th className="text-right text-slate-400 font-medium pb-2 pr-3">Target</th>
                    <th className="text-right text-slate-400 font-medium pb-2">Status</th>
                  </tr>
                </thead>
                <tbody>
                  {result.comparisonTable.map((row) => (
                    <tr key={row.key} className="border-b border-slate-50 last:border-0">
                      <td className="py-2 pr-3 text-slate-700 font-medium">{row.label}</td>
                      <td className="py-2 pr-3 text-right text-slate-900 font-semibold">
                        {row.scenarioValue}
                        <span className="text-slate-400 font-normal ml-0.5 text-xs">
                          {row.key === "co2" ? "g" : row.key === "policy" ? "%" : row.key === "cost" ? "$" : ""}
                        </span>
                      </td>
                      <td className="py-2 pr-3 text-right text-slate-500">
                        {row.benchmarkValue}
                        <span className="text-slate-300 ml-0.5">
                          {row.key === "co2" ? "g" : row.key === "policy" ? "%" : row.key === "cost" ? "$" : ""}
                        </span>
                      </td>
                      <td className="py-2 text-right">
                        <ReadingBadge reading={row.readingColor} />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <p className="text-xs text-slate-300 mt-3">
                Ref flight: {result.refFlight} · {result.aircraftLabel.split("(")[0].trim()}
              </p>
            </div>

            {/* Source footer */}
            <div className="text-xs text-slate-400 leading-relaxed px-1">
              Sources: IATA-CR 2024 · ICAO CAEP/12 2022 · CORSIA 2022 · ReFuelEU Regulation 2023/2405 ·
              EU ETS reference $80/tCO₂ · Jet-A ref $700/t · ASTM D1655
            </div>
          </div>
        </div>
      </div>

      {/* ── Footer ───────────────────────────────────────────────────────────── */}
      <footer className="border-t border-slate-200 py-6 px-4 sm:px-6 mt-8">
        <div className="max-w-7xl mx-auto flex flex-col sm:flex-row items-center justify-between gap-2">
          <span className="text-sm tracking-tight">
            <span className="font-bold text-slate-900">Polaris</span>
            <span className="font-light text-slate-400"> Systems</span>
          </span>
          <p className="text-xs text-slate-400">
            Engineering clarity for complex futures · Tool outputs are for analytical exploration only and do not constitute regulatory or financial advice.
          </p>
        </div>
      </footer>
    </div>
  );
}
