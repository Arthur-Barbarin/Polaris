// FAA regulatory compliance check (US, as of June 2026).
//
// References:
//   14 CFR Part 107          — sUAS operating rules (commercial)
//   14 CFR §107.31           — VLOS requirement
//   14 CFR §107.29           — Night ops (anti-collision lighting required;
//                                waiver-free since the April 2021 rulemaking)
//   14 CFR §107.140–145      — Operations Over People, Categories 1–4
//   14 CFR Part 89           — Remote ID (enforced from Sep 16, 2023)
//   Part 108 NPRM (Aug 2025) — BVLOS normalization; final rule still pending
//                               as of June 2026, expected Q3-Q4 2026
//
// LAANC = Low Altitude Authorization and Notification Capability — the
// near-real-time API that grants Part 107 authorization to fly in controlled
// airspace (B/C/D/E surface) up to per-grid ceilings published in the FAA
// UAS Facility Maps.

export const FAA_RULES = {
  part_107_max_alt_ft: 400,
  part_107_max_speed_mph: 100,
  part_107_max_mtow_lb: 55,
  rid_required_above_lb: 0.55, // > 250 g
};

export function checkCompliance({
  drone,
  max_altitude_ft,
  vlos,
  controlled_airspace,
  over_people,
  night,
}) {
  const findings = [];
  let allow = true;

  // ── Weight ──────────────────────────────────────────────
  const mtow_lb = drone.mtow_kg * 2.2046;
  if (mtow_lb > FAA_RULES.part_107_max_mtow_lb) {
    findings.push({
      level: "block",
      text: `MTOW ${drone.mtow_kg} kg (${mtow_lb.toFixed(1)} lb) exceeds Part 107 25 kg / 55 lb ceiling. Requires §44807 exemption or future Part 108 certification.`,
    });
    allow = false;
  } else {
    findings.push({
      level: "ok",
      text: `MTOW ${drone.mtow_kg} kg within Part 107 (≤25 kg).`,
    });
  }

  // ── Remote ID ───────────────────────────────────────────
  if (mtow_lb > FAA_RULES.rid_required_above_lb) {
    if (drone.has_rid) {
      findings.push({
        level: "ok",
        text: "Remote ID compliant (14 CFR Part 89 — enforced since Sep 2023).",
      });
    } else {
      findings.push({
        level: "block",
        text: "Drone exceeds 250 g without Remote ID — operation prohibited.",
      });
      allow = false;
    }
  }

  // ── Altitude ────────────────────────────────────────────
  if (max_altitude_ft > FAA_RULES.part_107_max_alt_ft) {
    findings.push({
      level: "warn",
      text: `Planned ${max_altitude_ft} ft AGL above 400 ft Part 107 ceiling. Allowed only within 400 ft of a structure, or via waiver.`,
    });
  } else {
    findings.push({
      level: "ok",
      text: `Altitude ${max_altitude_ft} ft within 400 ft AGL Part 107 ceiling.`,
    });
  }

  // ── Speed ───────────────────────────────────────────────
  const cruise_mph = drone.cruise_ms * 2.2369;
  if (cruise_mph > FAA_RULES.part_107_max_speed_mph) {
    findings.push({
      level: "warn",
      text: `Cruise ${cruise_mph.toFixed(0)} mph above Part 107 100 mph limit — requires §107.51(b) waiver.`,
    });
  }

  // ── VLOS / BVLOS ────────────────────────────────────────
  if (vlos) {
    findings.push({
      level: "ok",
      text: "VLOS — operated within visual line of sight per §107.31.",
    });
  } else {
    if (drone.bvlos_authorized) {
      findings.push({
        level: "warn",
        text: "BVLOS — operator holds FAA authorization (Part 135 air carrier and/or §44807 exemption). Verify corridor is in approved ConOps.",
      });
    } else {
      findings.push({
        level: "block",
        text: "BVLOS — no listed authorization. Part 108 NPRM published Aug 2025; final rule pending (expected late 2026). Requires §107.31 waiver in the interim.",
      });
      allow = false;
    }
  }

  // ── Controlled airspace ─────────────────────────────────
  if (controlled_airspace) {
    findings.push({
      level: "warn",
      text: "Controlled airspace (Class B/C/D or E to surface) — LAANC authorization required; ceiling per UAS Facility Map grid.",
    });
  } else {
    findings.push({
      level: "ok",
      text: "Class G airspace — no LAANC required.",
    });
  }

  // ── Over people ─────────────────────────────────────────
  if (over_people) {
    findings.push({
      level: "warn",
      text: "Operation over people — requires Category 1–4 eligibility (§107.140–145): kinetic energy limits, no exposed rotating parts, Declaration of Compliance.",
    });
  }

  // ── Night ───────────────────────────────────────────────
  if (night) {
    findings.push({
      level: "warn",
      text: "Night operation — anti-collision lighting visible 3 statute miles required (§107.29). Waiver-free since April 2021.",
    });
  }

  return { allow, findings };
}
