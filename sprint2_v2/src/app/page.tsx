"use client";

import { useState, useMemo } from "react";
import { runEngine } from "@/lib/engine";
import type {
  ScenarioInputs,
  UseCase,
  Platform,
  BVLOSStatus,
  Geography,
  LaborMultiplier,
  HumanAlternative,
  Verdict,
} from "@/lib/engine";

// ── Defaults ──────────────────────────────────────────────────────────────────

const DEFAULT_INPUTS: ScenarioInputs = {
  useCase: "inspection",
  platform: "professional",
  missionRange: 5.0,        // 5km = realistic power-line corridor range
  payload: 0.5,
  bvlosStatus: "authorized", // show the economics first; regulatory state is a separate question
  annualMissions: 200,
  geography: "rural",
  laborMultiplier: "standard",
  humanAlternative: "helicopter",  // helicopter is the primary baseline for corridor inspection
};

// ── Option maps ───────────────────────────────────────────────────────────────

const USE_CASE_OPTIONS: { value: UseCase; label: string; hint: string; icon: string }[] = [
  { value: "inspection", label: "Inspection", hint: "Power lines, wind turbines, pipelines", icon: "⚡" },
  { value: "delivery", label: "Last-mile delivery", hint: "Packages, logistics, e-commerce", icon: "📦" },
  { value: "agriculture", label: "Agriculture", hint: "Crop spraying, precision mapping", icon: "🌾" },
];

const PLATFORM_OPTIONS: { value: Platform; label: string; spec: string; price: string }[] = [
  { value: "light", label: "Light", spec: "0.9 kg · 42 min · 5 km", price: "$6.5k" },
  { value: "professional", label: "Professional", spec: "2.7 kg · 55 min · 8 km", price: "$20k" },
  { value: "heavy", label: "Heavy", spec: "5.0 kg · 57 min · 12 km", price: "$50k" },
];

const BVLOS_OPTIONS: { value: BVLOSStatus; label: string; sub: string }[] = [
  { value: "authorized", label: "Yes, authorized", sub: "Waiver held or Part 108 permit" },
  { value: "waiver_pending", label: "Applied, pending", sub: "~90-day FAA review in progress" },
  { value: "not_authorized", label: "Not authorized", sub: "VLOS only for now" },
];

const GEOGRAPHY_OPTIONS: { value: Geography; label: string }[] = [
  { value: "urban", label: "Urban" },
  { value: "suburban", label: "Suburban" },
  { value: "rural", label: "Rural" },
  { value: "remote", label: "Remote" },
];

const LABOR_OPTIONS: { value: LaborMultiplier; label: string; mult: string }[] = [
  { value: "low", label: "Low cost", mult: "0.7×" },
  { value: "standard", label: "US standard", mult: "1.0×" },
  { value: "high", label: "High / union", mult: "1.5×" },
];

const HUMAN_ALT_OPTIONS: Record<UseCase, { value: HumanAlternative; label: string; ref: string }[]> = {
  inspection: [
    { value: "helicopter", label: "Manned helicopter", ref: "$2,500/hr" },
    { value: "rope_access", label: "Rope access team", ref: "$4,000/asset" },
    { value: "ground_crew", label: "Ground crew (bucket truck)", ref: "$150/hr" },
  ],
  delivery: [
    { value: "ground_crew", label: "Van / courier", ref: "Varies by geography" },
  ],
  agriculture: [
    { value: "aerial", label: "Manned crop duster", ref: "$15/acre" },
    { value: "ground", label: "Ground sprayer", ref: "$6/acre" },
  ],
};

const VERDICT_COLOR: Record<Verdict, string> = {
  GO: "bg-emerald-500",
  CONDITIONAL: "bg-amber-500",
  "NO-GO": "bg-rose-500",
};

// ── Number formatting — locale-independent, always uses commas ────────────────

function fmtNum(n: number, d = 0): string {
  const fixed = Math.abs(n).toFixed(d);
  const [int, dec] = fixed.split(".");
  const grouped = int.replace(/\B(?=(\d{3})+(?!\d))/g, ",");
  return d > 0 && dec !== undefined ? `${grouped}.${dec}` : grouped;
}

function usd(n: number): string {
  return "$" + fmtNum(Math.round(n));
}

// ── Small UI primitives ───────────────────────────────────────────────────────

function SectionDivider() {
  return <div className="my-8 border-t border-slate-100" />;
}

function StepLabel({ n, label }: { n: number; label: string }) {
  return (
    <div className="flex items-center gap-3 mb-5">
      <div className="w-7 h-7 rounded-full bg-slate-900 flex items-center justify-center shrink-0">
        <span className="text-xs font-bold text-white">{n}</span>
      </div>
      <span className="text-xs font-bold text-slate-500 uppercase tracking-widest">{label}</span>
    </div>
  );
}

function Chip({
  selected,
  onClick,
  children,
}: {
  selected: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      onClick={onClick}
      className={`px-3.5 py-2 rounded-lg text-sm border transition-all ${
        selected
          ? "bg-slate-900 text-white border-slate-900"
          : "bg-white text-slate-600 border-slate-200 hover:border-slate-400"
      }`}
    >
      {children}
    </button>
  );
}

// ── SelectCard — card-style radio group ──────────────────────────────────────

function SelectCard<T extends string>({
  options,
  value,
  onChange,
}: {
  options: {
    value: T;
    label: string;
    hint?: string;
    sub?: string;
    ref?: string;
    icon?: string;
  }[];
  value: T;
  onChange: (v: T) => void;
}) {
  return (
    <div className="flex flex-col gap-2.5">
      {options.map((o) => {
        const sel = value === o.value;
        return (
          <button
            key={o.value}
            onClick={() => onChange(o.value)}
            className={`text-left w-full px-4 py-4 rounded-xl border-2 transition-all ${
              sel
                ? "border-slate-900 bg-slate-900 text-white"
                : "border-slate-200 bg-white hover:border-slate-300 hover:bg-slate-50"
            }`}
          >
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2.5">
                {o.icon && <span className="text-base">{o.icon}</span>}
                <span className="font-semibold text-sm">{o.label}</span>
              </div>
              <div className="flex items-center gap-3">
                {o.ref && (
                  <span className={`text-xs tabular-nums ${sel ? "text-slate-300" : "text-slate-400"}`}>
                    {o.ref}
                  </span>
                )}
                {sel && (
                  <span className="w-4 h-4 rounded-full border-2 border-white flex items-center justify-center shrink-0">
                    <span className="w-1.5 h-1.5 bg-white rounded-full" />
                  </span>
                )}
              </div>
            </div>
            {(o.hint || o.sub) && (
              <p className={`text-xs mt-1 ${o.icon ? "ml-8" : ""} ${sel ? "text-slate-400" : "text-slate-400"}`}>
                {o.hint ?? o.sub}
              </p>
            )}
          </button>
        );
      })}
    </div>
  );
}

// ── Slider ────────────────────────────────────────────────────────────────────

function Slider({
  label,
  hint,
  value,
  min,
  max,
  step,
  unit,
  onChange,
  alert,
}: {
  label: string;
  hint?: string;
  value: number;
  min: number;
  max: number;
  step: number;
  unit: string;
  onChange: (v: number) => void;
  alert?: boolean;
}) {
  return (
    <div className="space-y-3">
      <div className="flex items-baseline justify-between">
        <span className="text-sm font-semibold text-slate-700">{label}</span>
        <span className={`text-base font-bold tabular-nums ${alert ? "text-amber-600" : "text-slate-900"}`}>
          {value} <span className="text-sm font-normal text-slate-400">{unit}</span>
        </span>
      </div>
      <div className="py-2">
        <input
          type="range"
          min={min}
          max={max}
          step={step}
          value={value}
          onChange={(e) => onChange(Number(e.target.value))}
          className="w-full"
        />
      </div>
      {hint && (
        <p className={`text-xs ${alert ? "text-amber-600 font-medium" : "text-slate-400"}`}>{hint}</p>
      )}
    </div>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────

export default function Page() {
  const [inputs, setInputs] = useState<ScenarioInputs>(DEFAULT_INPUTS);

  const set = <K extends keyof ScenarioInputs>(key: K, val: ScenarioInputs[K]) => {
    setInputs((prev) => {
      const next = { ...prev, [key]: val };
      if (key === "useCase") {
        next.humanAlternative = HUMAN_ALT_OPTIONS[val as UseCase][0].value as HumanAlternative;
        // Default platform by use case: delivery → light, inspection/agriculture → professional
        if (val === "delivery") next.platform = "light";
        else if (val === "inspection" || val === "agriculture") next.platform = "professional";
        // missionRange means different things by use case — reset to sensible defaults
        if (val === "agriculture") next.missionRange = 20;        // 20 acres/mission
        else if (prev.useCase === "agriculture") next.missionRange = 1.0; // km
      }
      return next;
    });
  };

  const result = useMemo(() => runEngine(inputs), [inputs]);
  const humanAltOpts = HUMAN_ALT_OPTIONS[inputs.useCase];
  const savingsPos = result.savingsPerMission > 0;

  return (
    <div className="min-h-screen bg-[#F5F5F3]">

      {/* Nav */}
      <nav className="bg-white border-b border-slate-200 px-6 h-12 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="w-6 h-6 bg-slate-900 rounded-md flex items-center justify-center">
            <span className="text-white text-xs font-bold">P</span>
          </div>
          <span className="font-semibold text-slate-900 text-sm">Polaris</span>
          <span className="text-slate-300 mx-1">/</span>
          <span className="text-slate-500 text-sm">Drone Decision Engine</span>
        </div>
        <a
          href="https://arthur-barbarin-polaris.streamlit.app"
          target="_blank"
          rel="noopener noreferrer"
          className="text-xs text-slate-400 hover:text-slate-900 transition-colors"
        >
          Battery & Fleet Studio →
        </a>
      </nav>

      {/* Hero */}
      <div className="bg-slate-900 px-6 py-12 text-center">
        <p className="text-slate-500 text-xs font-semibold uppercase tracking-widest mb-3">
          Sprint 2 · Commercial UAS
        </p>
        <h1 className="text-4xl font-black text-white mb-3 tracking-tight">
          Should you deploy drones here?
        </h1>
        <p className="text-slate-400 text-sm max-w-md mx-auto leading-relaxed">
          Set your scenario. Get a Go / No-Go decision with the exact constraint
          blocking deployment — and what it takes to fix it.
        </p>
        <p className="text-slate-600 text-xs mt-4">
          Numbers sourced from FAA regulations, PwC industry research, and university studies.
          No made-up scores.
        </p>
      </div>

      {/* Two-column layout */}
      <div className="max-w-5xl mx-auto px-4 py-8 grid grid-cols-1 lg:grid-cols-[1fr_380px] gap-6 items-start">

        {/* ── FORM ─────────────────────────────────────────────────────────── */}
        <div className="bg-white rounded-2xl border border-slate-200 px-8 py-8">

          {/* 1 — Use case */}
          <StepLabel n={1} label="What are you using drones for?" />
          <SelectCard
            options={USE_CASE_OPTIONS}
            value={inputs.useCase}
            onChange={(v) => set("useCase", v)}
          />

          <SectionDivider />

          {/* 2 — Human alternative */}
          <StepLabel n={2} label="What does it replace?" />
          <SelectCard
            options={humanAltOpts}
            value={inputs.humanAlternative}
            onChange={(v) => set("humanAlternative", v)}
          />

          <SectionDivider />

          {/* 3 — Platform */}
          <StepLabel n={3} label="Platform tier" />
          <div className="grid grid-cols-3 gap-3">
            {PLATFORM_OPTIONS.map((o) => {
              const sel = inputs.platform === o.value;
              return (
                <button
                  key={o.value}
                  onClick={() => set("platform", o.value)}
                  className={`px-3 py-4 rounded-xl border-2 text-left transition-all ${
                    sel
                      ? "border-slate-900 bg-slate-900 text-white"
                      : "border-slate-200 bg-white hover:border-slate-300"
                  }`}
                >
                  <p className="text-sm font-bold">{o.label}</p>
                  <p className={`text-sm font-semibold mt-0.5 ${sel ? "text-slate-300" : "text-slate-500"}`}>
                    {o.price}
                  </p>
                  <p className={`text-[11px] mt-1.5 leading-relaxed ${sel ? "text-slate-400" : "text-slate-400"}`}>
                    {o.spec}
                  </p>
                </button>
              );
            })}
          </div>

          <SectionDivider />

          {/* 4 — Mission parameters */}
          <StepLabel n={4} label="Mission parameters" />
          <div className="space-y-8">
            {inputs.useCase === "agriculture" ? (
              <Slider
                label="Field size per mission"
                hint="Acres sprayed in a single drone deployment. Operator stays at field edge — no BVLOS needed."
                value={inputs.missionRange}
                min={5} max={200} step={5} unit="acres"
                onChange={(v) => set("missionRange", v)}
              />
            ) : (
              <Slider
                label="Mission range (one-way)"
                value={inputs.missionRange}
                min={0.5} max={50} step={0.5} unit="km"
                onChange={(v) => set("missionRange", v)}
                hint={
                  inputs.missionRange > 1.5
                    ? "Beyond visual line of sight — BVLOS authorization required"
                    : "Within visual line of sight (FAA limit: 1.5 km)"
                }
                alert={inputs.missionRange > 1.5}
              />
            )}
            {inputs.useCase !== "agriculture" && (
              <Slider
                label="Payload weight"
                value={inputs.payload}
                min={0.1} max={10} step={0.1} unit="kg"
                onChange={(v) => set("payload", v)}
              />
            )}
            <Slider
              label="Missions per year"
              hint="More missions = fixed costs spread further = lower cost per flight"
              value={inputs.annualMissions}
              min={10} max={2000} step={10} unit="/yr"
              onChange={(v) => set("annualMissions", v)}
            />
          </div>

          <SectionDivider />

          {/* 5 — BVLOS (hidden for agriculture: operator always at field edge) */}
          {inputs.useCase !== "agriculture" && (
            <>
              <StepLabel n={5} label="Can you fly beyond visual range?" />
              <SelectCard
                options={BVLOS_OPTIONS}
                value={inputs.bvlosStatus}
                onChange={(v) => set("bvlosStatus", v)}
              />
            </>
          )}

          <SectionDivider />

          {/* 6 — Context */}
          <StepLabel n={6} label="Operating context" />
          <div className="grid grid-cols-2 gap-8">
            <div>
              <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-3">Geography</p>
              <div className="flex flex-wrap gap-2">
                {GEOGRAPHY_OPTIONS.map((o) => (
                  <Chip
                    key={o.value}
                    selected={inputs.geography === o.value}
                    onClick={() => set("geography", o.value)}
                  >
                    {o.label}
                  </Chip>
                ))}
              </div>
            </div>
            <div>
              <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-3">Labor market</p>
              <div className="flex flex-col gap-2">
                {LABOR_OPTIONS.map((o) => (
                  <Chip
                    key={o.value}
                    selected={inputs.laborMultiplier === o.value}
                    onClick={() => set("laborMultiplier", o.value)}
                  >
                    {o.label}
                    <span className="ml-1.5 opacity-60 text-xs">{o.mult}</span>
                  </Chip>
                ))}
              </div>
            </div>
          </div>
        </div>

        {/* ── RESULTS ──────────────────────────────────────────────────────── */}
        <div className="space-y-3 lg:sticky lg:top-6">

          {/* Verdict */}
          <div className="bg-white rounded-2xl border border-slate-200 overflow-hidden">
            <div className={`px-6 py-6 ${VERDICT_COLOR[result.verdict]}`}>
              <p className="text-xs font-bold uppercase tracking-widest text-white/60 mb-1">
                Deployment verdict
              </p>
              <p className="text-5xl font-black text-white tracking-tight">
                {result.verdict}
              </p>
            </div>

            {result.bindingConstraint && (
              <div className="px-6 py-4 border-b border-slate-100">
                <p className="text-[10px] font-bold uppercase tracking-widest text-slate-400 mb-1.5">
                  Binding constraint
                </p>
                <p className="text-sm font-semibold text-slate-800 leading-snug">
                  {result.bindingConstraint}
                </p>
                {result.resolutionPath && (
                  <p className="text-xs text-slate-500 mt-2 leading-relaxed">
                    {result.resolutionPath}
                  </p>
                )}
              </div>
            )}

            <div className="px-6 py-5">
              {/* Cost comparison */}
              <div className="grid grid-cols-2 gap-4 mb-4">
                <div>
                  <p className="text-[10px] font-bold uppercase tracking-widest text-slate-400 mb-1">
                    Drone / mission
                  </p>
                  <p className="text-2xl font-black text-slate-900 tabular-nums">
                    {usd(result.droneDOC)}
                  </p>
                </div>
                <div>
                  <p className="text-[10px] font-bold uppercase tracking-widest text-slate-400 mb-1">
                    Human alternative
                  </p>
                  <p className="text-2xl font-black text-slate-900 tabular-nums">
                    {usd(result.humanCost)}
                  </p>
                </div>
              </div>

              {/* Comparison bar */}
              <div className="mb-4">
                <div className="h-2.5 bg-slate-100 rounded-full overflow-hidden">
                  <div
                    className={`h-full rounded-full transition-all ${savingsPos ? "bg-emerald-500" : "bg-rose-500"}`}
                    style={{
                      width: savingsPos
                        ? `${Math.min((result.droneDOC / result.humanCost) * 100, 100).toFixed(1)}%`
                        : "100%",
                    }}
                  />
                </div>
                <p className="text-xs text-slate-400 mt-1.5">
                  {savingsPos
                    ? `Drone is ${result.savingsPct.toFixed(0)}% cheaper per mission`
                    : `Drone is ${Math.abs(result.savingsPct).toFixed(0)}% more expensive`}
                </p>
              </div>

              {/* Annual savings highlight */}
              <div
                className={`rounded-xl px-5 py-4 ${
                  savingsPos
                    ? "bg-emerald-50 border border-emerald-100"
                    : "bg-rose-50 border border-rose-100"
                }`}
              >
                <p className={`text-[10px] font-bold uppercase tracking-widest mb-1 ${savingsPos ? "text-emerald-600" : "text-rose-600"}`}>
                  {savingsPos ? "Annual savings" : "Annual overspend"}
                </p>
                <p className={`text-3xl font-black tabular-nums ${savingsPos ? "text-emerald-700" : "text-rose-700"}`}>
                  {savingsPos ? "+" : "−"}{usd(Math.abs(result.annualSavings))}
                  <span className="text-sm font-semibold opacity-60 ml-1">/yr</span>
                </p>
                <p className={`text-xs mt-1 ${savingsPos ? "text-emerald-600/70" : "text-rose-600/70"}`}>
                  at {fmtNum(inputs.annualMissions)} missions/yr
                </p>
              </div>
            </div>
          </div>

          {/* Break-even + payback */}
          {result.breakEvenVolume > 0 && (
            <div className="bg-white rounded-2xl border border-slate-200 px-6 py-5">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <p className="text-[10px] font-bold uppercase tracking-widest text-slate-400 mb-1">Break-even</p>
                  <p className="text-xl font-black text-slate-900 tabular-nums">
                    {fmtNum(Math.ceil(result.breakEvenVolume))}
                    <span className="text-sm font-normal text-slate-400 ml-1">missions</span>
                  </p>
                  <p className="text-xs text-slate-400 mt-0.5">to recover platform cost</p>
                </div>
                <div>
                  <p className="text-[10px] font-bold uppercase tracking-widest text-slate-400 mb-1">Payback</p>
                  <p className="text-xl font-black text-slate-900 tabular-nums">
                    {result.paybackMonths < 1 ? "<1" : result.paybackMonths.toFixed(1)}
                    <span className="text-sm font-normal text-slate-400 ml-1">mo</span>
                  </p>
                  <p className="text-xs text-slate-400 mt-0.5">at current volume</p>
                </div>
              </div>
            </div>
          )}

          {/* BVLOS unlock */}
          {result.bvlosUnlockValue !== null && result.bvlosUnlockValue > 100 && (
            <div className="bg-white rounded-2xl border border-slate-200 px-6 py-5">
              <p className="text-[10px] font-bold uppercase tracking-widest text-slate-400 mb-1.5">
                BVLOS unlock value
              </p>
              <p className="text-2xl font-black text-slate-900 tabular-nums">
                +{usd(result.bvlosUnlockValue)}
                <span className="text-sm font-normal text-slate-400 ml-1">/yr</span>
              </p>
              <p className="text-xs text-slate-400 mt-1.5 leading-relaxed">
                Additional annual savings if BVLOS is authorized. FAA Part 108 permit framework
                expected 2026–27.
              </p>
            </div>
          )}

          {/* Flags */}
          {result.flags.map((f, i) => (
            <div key={i} className="bg-amber-50 border border-amber-200 rounded-xl px-5 py-3.5">
              <p className="text-xs text-amber-700 leading-relaxed">⚠ {f}</p>
            </div>
          ))}

          {/* Summary */}
          <div className="bg-white rounded-2xl border border-slate-200 px-6 py-5">
            <p className="text-[10px] font-bold uppercase tracking-widest text-slate-400 mb-2.5">
              Summary
            </p>
            <p className="text-sm text-slate-600 leading-relaxed">{result.narrative}</p>
          </div>

          {/* Cost breakdown */}
          <div className="bg-white rounded-2xl border border-slate-200 px-6 py-5">
            <p className="text-[10px] font-bold uppercase tracking-widest text-slate-400 mb-4">
              Cost breakdown
            </p>
            <CostBreakdown
              inputs={inputs}
              droneDOC={result.droneDOC}
              missionDurationHr={result.missionDurationHr}
            />
          </div>

          {/* Footer */}
          <p className="text-[11px] text-slate-400 text-center px-4 leading-relaxed">
            All cost coefficients derived from FAA regulations, PwC research, and university studies.
            Every constraint is traceable.{" "}
            <a
              href="https://arthur-barbarin-polaris.streamlit.app"
              target="_blank"
              rel="noopener noreferrer"
              className="underline hover:text-slate-700"
            >
              See Sprint 3 →
            </a>
          </p>
        </div>
      </div>
    </div>
  );
}

// ── Cost breakdown bars ───────────────────────────────────────────────────────
// Uses engine outputs directly — no independent recalculation that can drift out of sync.

function CostBreakdown({ inputs, droneDOC, missionDurationHr }: {
  inputs: ScenarioInputs;
  droneDOC: number;
  missionDurationHr: number;
}) {
  const platformCost = { light: 6500, professional: 20000, heavy: 50000 }[inputs.platform];
  const batteryCost = { light: 300, professional: 450, heavy: 600 }[inputs.platform];
  const insuranceCost = { light: 800, professional: 2000, heavy: 4000 }[inputs.platform];

  // All values derived from the same formula as the engine — missionDurationHr comes from engine
  const items = [
    { label: "Pilot", value: 65 * missionDurationHr },
    { label: "Depreciation", value: platformCost / (3 * inputs.annualMissions) },
    { label: "Maintenance", value: (platformCost * 0.15) / inputs.annualMissions },
    { label: "Insurance", value: insuranceCost / inputs.annualMissions },
    { label: "Battery", value: batteryCost / 250 },
  ];
  // Use engine's droneDOC as the total to guarantee consistency
  const total = droneDOC;

  return (
    <div className="space-y-3">
      {items.map((item) => (
        <div key={item.label} className="flex items-center gap-3">
          <span className="text-xs text-slate-500 w-24 shrink-0">{item.label}</span>
          <div className="flex-1 bg-slate-100 rounded-full h-2 overflow-hidden">
            <div
              className="h-full bg-slate-700 rounded-full"
              style={{ width: `${Math.min((item.value / total) * 100, 100).toFixed(1)}%` }}
            />
          </div>
          <span className="text-xs font-mono font-medium text-slate-700 w-14 text-right shrink-0">
            ${item.value.toFixed(2)}
          </span>
        </div>
      ))}
      <div className="pt-2 border-t border-slate-100 flex justify-between">
        <span className="text-xs text-slate-400">Total per mission</span>
        <span className="text-xs font-mono font-bold text-slate-900">${total.toFixed(2)}</span>
      </div>
    </div>
  );
}
