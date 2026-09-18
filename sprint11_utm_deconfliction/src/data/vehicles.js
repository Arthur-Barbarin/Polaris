// eVTOL / UAM vehicle catalogue.
//
// HONESTY NOTE: cruise speeds are manufacturer-published nominal cruise figures
// (rounded). We do NOT model each type's full flight envelope — only the two
// numbers deconfliction needs: cruise ground speed and a nominal climb/descend
// rate for vertical resolution maneuvers. Climb rates are order-of-magnitude
// values typical of lift+cruise / multirotor eVTOLs (published rates are rarely
// disclosed), and are flagged as assumptions in MODEL.md.
//
// RANGE is modelled, because the fleet generator must not assign a vehicle a
// hop it cannot fly. Ranges are manufacturer-published maxima, with no reserve
// applied: this sprint carries no energy state (that is Sprints 3, 5, 6 and 7),
// so the figure is a feasibility ceiling, not an operational range.
//
// Sources: Joby SEC S-1 2021; Archer SEC 10-K 2023; Wisk press release 2023
// (the same figures Sprint 5 cites); Vertical Aerospace and Volocopter
// published spec pages.

export const VEHICLES = {
  volocity: {
    id: "volocity", name: "Volocopter VoloCity", class: "multirotor",
    cruise_ms: 25,   // ~90 km/h
    climb_ms: 2.5,
    range_km: 35,   // Volocopter published spec
    color: "#38bdf8",
  },
  midnight: {
    id: "midnight", name: "Archer Midnight", class: "lift+cruise",
    cruise_ms: 67,   // ~150 mph
    climb_ms: 5,
    range_km: 97,   // Archer SEC 10-K 2023
    color: "#a78bfa",
  },
  jobys4: {
    id: "jobys4", name: "Joby S4", class: "tiltrotor",
    cruise_ms: 89,   // ~200 mph
    climb_ms: 6,
    range_km: 240,   // Joby SEC S-1 2021
    color: "#f472b6",
  },
  vx4: {
    id: "vx4", name: "Vertical VX4", class: "lift+cruise",
    cruise_ms: 67,   // ~150 mph
    climb_ms: 5,
    range_km: 160,   // Vertical Aerospace published spec
    color: "#34d399",
  },
  wisk6: {
    id: "wisk6", name: "Wisk Gen 6", class: "lift+cruise",
    cruise_ms: 55,   // ~120 kt (autonomous)
    climb_ms: 4.5,
    range_km: 145,   // Wisk press release 2023
    color: "#fbbf24",
  },
};

export const VEHICLE_LIST = Object.values(VEHICLES);
