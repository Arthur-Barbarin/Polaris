// Preset no-fly polygons (Seattle area demo).
// Real-world equivalents would come from FAA UAS Facility Maps + TFRs.
// Each polygon is an octagon approximating the published controlled radius
// for Class B/C/D airfields around the planning area.

function octagon(centerLat, centerLng, radius_km) {
  const R = 6371;
  const dLatPerKm = 1 / 110.574;
  const dLngPerKm = 1 / (111.32 * Math.cos((centerLat * Math.PI) / 180));
  const pts = [];
  for (let i = 0; i < 8; i++) {
    const theta = (i * 2 * Math.PI) / 8;
    pts.push({
      lat: centerLat + radius_km * Math.sin(theta) * dLatPerKm,
      lng: centerLng + radius_km * Math.cos(theta) * dLngPerKm,
    });
  }
  return pts;
}

export const NO_FLY_PRESETS = [
  {
    id: "ksea",
    name: "Seattle–Tacoma Intl (KSEA) Class B core",
    description: "Approx. 5 nm core; real Class B has tiered shelves.",
    color: "#d62728",
    polygon: octagon(47.4502, -122.3088, 6.0),
    enabled_by_default: true,
  },
  {
    id: "kbfi",
    name: "Boeing Field (KBFI) Class D",
    description: "Approx. 4 nm radius.",
    color: "#d62728",
    polygon: octagon(47.5301, -122.3025, 4.5),
    enabled_by_default: true,
  },
  {
    id: "krnt",
    name: "Renton Muni (KRNT) Class D",
    description: "Approx. 3.5 nm radius.",
    color: "#d62728",
    polygon: octagon(47.4931, -122.2156, 3.5),
    enabled_by_default: false,
  },
];
