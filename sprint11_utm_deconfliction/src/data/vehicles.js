// eVTOL / UAM vehicle catalogue.
//
// HONESTY NOTE: cruise speeds are manufacturer-published nominal cruise figures
// (rounded). We do NOT model each type's full flight envelope — only the two
// numbers deconfliction needs: cruise ground speed and a nominal climb/descend
// rate for vertical resolution maneuvers. Climb rates are order-of-magnitude
// values typical of lift+cruise / multirotor eVTOLs (published rates are rarely
// disclosed), and are flagged as assumptions in MODEL.md.
//
// Sources: manufacturer spec pages / press kits (Joby S4, Archer Midnight,
// Vertical VX4, Volocopter VoloCity, Wisk Gen 6).

export const VEHICLES = {
  volocity: {
    id: "volocity", name: "Volocopter VoloCity", class: "multirotor",
    cruise_ms: 25,   // ~90 km/h
    climb_ms: 2.5,
    color: "#38bdf8",
  },
  midnight: {
    id: "midnight", name: "Archer Midnight", class: "lift+cruise",
    cruise_ms: 67,   // ~150 mph
    climb_ms: 5,
    color: "#a78bfa",
  },
  jobys4: {
    id: "jobys4", name: "Joby S4", class: "tiltrotor",
    cruise_ms: 89,   // ~200 mph
    climb_ms: 6,
    color: "#f472b6",
  },
  vx4: {
    id: "vx4", name: "Vertical VX4", class: "lift+cruise",
    cruise_ms: 67,   // ~150 mph
    climb_ms: 5,
    color: "#34d399",
  },
  wisk6: {
    id: "wisk6", name: "Wisk Gen 6", class: "lift+cruise",
    cruise_ms: 55,   // ~120 kt (autonomous)
    climb_ms: 4.5,
    color: "#fbbf24",
  },
};

export const VEHICLE_LIST = Object.values(VEHICLES);
