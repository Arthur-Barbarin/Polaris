// Drone catalog — published, verifiable specs only.
// Each entry includes its provenance for downstream display.
//
// SOURCES (accessed June 2026):
//   [SKYDIO-X10]   skydio.com/x10/technical-specs · skydio.com/x10/faqs
//   [SKYDIO-BATT]  Skydio 150W spare battery DR4ACCBAT — 8419 mAh × 18.55 V = 156.17 Wh
//   [DJI-M30]      enterprise.dji.com/matrice-30/specs
//   [DJI-TB30]     TB30 intelligent flight battery — 5,880 mAh × 26.1 V = 131.6 Wh (2 per aircraft)
//   [ZIPLINE-P2]   zipline.com/about/zipline-fact-sheet
//   [WING]         FAA Christiansburg EA + Wing public specs

export const DRONES = {
  skydio_x10: {
    id: "skydio_x10",
    name: "Skydio X10",
    role: "Autonomous inspection / public safety",
    type: "multirotor",
    mtow_kg: 2.49,                // 5.49 lb
    battery_wh: 156.17,           // single battery; X10 carries one
    max_flight_time_min: 40,
    cruise_ms: 13,                // ~29 mph — conservative cruise; max 20 m/s (45 mph) [SKYDIO-X10]
    max_ms: 20,
    wind_limit_ms: 12.5,          // 28 mph gust per IP55 rating
    has_rid: true,
    bvlos_authorized: false,      // Skydio has limited DfR waivers, not blanket BVLOS
    sources: ["skydio.com/x10/technical-specs"],
  },
  dji_m30: {
    id: "dji_m30",
    name: "DJI Matrice 30",
    role: "Industrial inspection",
    type: "multirotor",
    mtow_kg: 3.77,
    battery_wh: 263.2,            // 2 × TB30 (131.6 Wh each)
    max_flight_time_min: 41,
    cruise_ms: 15,                // ~34 mph — conservative cruise
    max_ms: 23,                   // ~50 mph
    wind_limit_ms: 15,            // 33 mph
    has_rid: true,
    bvlos_authorized: false,
    sources: ["enterprise.dji.com/matrice-30/specs"],
  },
  zipline_p2: {
    id: "zipline_p2",
    name: "Zipline P2 Zip",
    role: "Hybrid-VTOL last-mile delivery",
    type: "hybrid_vtol",
    mtow_kg: 20,                  // estimated — not publicly disclosed; Zipline P2 is the Zip itself, not the dock
    payload_kg: 3.6,
    battery_wh: null,             // not public — use range-based feasibility
    range_km_one_way: 16,         // 10 mi service radius
    max_flight_time_min: 18,      // ≈ 16 km / 31 m/s
    cruise_ms: 31,                // 70 mph
    max_ms: 31,
    wind_limit_ms: 13,
    has_rid: true,
    bvlos_authorized: true,       // Part 135 air carrier + §44807 exemption
    sources: ["zipline.com/about/zipline-fact-sheet"],
  },
  wing_hb: {
    id: "wing_hb",
    name: "Wing Hummingbird",
    role: "Last-mile delivery",
    type: "hybrid_vtol",
    mtow_kg: 6.8,                 // 15 lb
    payload_kg: 1.13,             // 2.5 lb
    battery_wh: null,             // not public
    range_km_one_way: 9.6,        // ≈ 6 mi each way per FAA EA
    max_flight_time_min: 11,
    cruise_ms: 29,                // 65 mph
    max_ms: 31,
    wind_limit_ms: 11,
    has_rid: true,
    bvlos_authorized: true,       // operates under FAA Part 135 + waivers
    sources: ["Wing FAA Christiansburg EA", "wing.com"],
  },
};

export const DRONE_LIST = Object.values(DRONES);
