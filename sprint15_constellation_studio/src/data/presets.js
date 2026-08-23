// Real constellation presets.
//
// HONESTY NOTE: these are the PUBLISHED design parameters of each system
// (nominal shell altitude, inclination, plane count, satellites per plane).
// They are NOT live ephemeris — this studio propagates idealised circular
// orbits from these design parameters, it does not ingest TLEs. Real
// constellations have multiple shells, spares, drifting phases and
// station-keeping; only the primary shell is modelled here.
//
// Sources: operator filings / published system descriptions
//  - Iridium NEXT: 66 operational sats, 6 planes, 780 km, 86.4°, Walker Star.
//  - OneWeb: 648-sat design, 18 planes, 1200 km, 87.9°, Walker Star.
//  - Starlink Gen1 shell 1: 1584 sats, 72 planes × 22, 550 km, 53.0°, Walker Delta.
//  - GPS: 24-slot baseline, 6 planes × 4, ~20 180 km, 55°.
//  - Galileo: 24 slots, 3 planes × 8, ~23 222 km, 56°.
//  - Sun-synchronous EO reference: ~500 km, i solved for SSO (≈97.4°).

export const PRESETS = {
  iridium: {
    id: "iridium", name: "Iridium NEXT",
    alt_km: 780, inc_deg: 86.4, planes: 6, satsPerPlane: 11,
    pattern: "star", phasing: 0, minElev_deg: 8.2,
    note: "66 sats — the classic continuously-covering LEO voice/data constellation.",
  },
  oneweb: {
    id: "oneweb", name: "OneWeb",
    alt_km: 1200, inc_deg: 87.9, planes: 18, satsPerPlane: 36,
    pattern: "star", phasing: 0, minElev_deg: 15,
    note: "648-sat design; higher shell means fewer sats for the same coverage.",
  },
  starlink: {
    id: "starlink", name: "Starlink Gen1 (shell 1)",
    alt_km: 550, inc_deg: 53.0, planes: 72, satsPerPlane: 22,
    pattern: "delta", phasing: 1, minElev_deg: 25,
    note: "1584 sats at 53° — dense mid-latitude coverage, no polar coverage.",
  },
  gps: {
    id: "gps", name: "GPS (baseline 24)",
    alt_km: 20180, inc_deg: 55, planes: 6, satsPerPlane: 4,
    pattern: "delta", phasing: 1, minElev_deg: 5,
    note: "MEO — huge footprints, so 24 sats give global multi-fold coverage.",
  },
  galileo: {
    id: "galileo", name: "Galileo",
    alt_km: 23222, inc_deg: 56, planes: 3, satsPerPlane: 8,
    pattern: "delta", phasing: 1, minElev_deg: 5,
    note: "MEO Walker 24/3/1.",
  },
  sso: {
    id: "sso", name: "SSO imaging (small)",
    alt_km: 500, inc_deg: 97.4, planes: 3, satsPerPlane: 4,
    pattern: "star", phasing: 0, minElev_deg: 20,
    note: "Sun-synchronous Earth-observation style shell — revisit-limited, not continuous.",
  },
};

export const PRESET_LIST = Object.values(PRESETS);

// Ground sites for the revisit / gap analysis.
export const SITES = [
  { id: "paris",     name: "Paris",          lat: 48.8566, lng: 2.3522 },
  { id: "seattle",   name: "Seattle",        lat: 47.6062, lng: -122.3321 },
  { id: "singapore", name: "Singapore",      lat: 1.3521,  lng: 103.8198 },
  { id: "nairobi",   name: "Nairobi",        lat: -1.2921, lng: 36.8219 },
  { id: "svalbard",  name: "Svalbard (78°N)", lat: 78.2232, lng: 15.6267 },
  { id: "mcmurdo",   name: "McMurdo (78°S)",  lat: -77.8419, lng: 166.6863 },
];
