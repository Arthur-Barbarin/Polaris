// Hand-drawn water polygons for the Seattle area (approximate).
// Used to block start/goal placement over water — drones still transit through
// water cells freely; we only reject endpoint clicks.
//
// For production, replace with OSM water tiles (Coastline / Waterways) or
// NOAA shoreline. The named shapes below are intentionally coarse so they
// don't snag legitimate shoreline clicks.

export const WATER_BODIES = [
  {
    id: "lake_wa_north",
    name: "Lake Washington (north of Mercer Island)",
    polygon: [
      { lat: 47.755, lng: -122.275 },
      { lat: 47.755, lng: -122.245 },
      { lat: 47.740, lng: -122.240 },
      { lat: 47.700, lng: -122.235 },
      { lat: 47.660, lng: -122.245 },
      { lat: 47.625, lng: -122.255 },
      { lat: 47.625, lng: -122.275 },
      { lat: 47.680, lng: -122.285 },
      { lat: 47.730, lng: -122.285 },
    ],
  },
  {
    id: "lake_wa_south",
    name: "Lake Washington (south of Mercer Island)",
    polygon: [
      { lat: 47.555, lng: -122.255 },
      { lat: 47.555, lng: -122.225 },
      { lat: 47.530, lng: -122.215 },
      { lat: 47.505, lng: -122.210 },
      { lat: 47.495, lng: -122.230 },
      { lat: 47.520, lng: -122.260 },
      { lat: 47.545, lng: -122.265 },
    ],
  },
  {
    id: "elliott_bay",
    name: "Elliott Bay",
    polygon: [
      { lat: 47.620, lng: -122.380 },
      { lat: 47.610, lng: -122.350 },
      { lat: 47.590, lng: -122.345 },
      { lat: 47.565, lng: -122.365 },
      { lat: 47.565, lng: -122.405 },
      { lat: 47.610, lng: -122.415 },
    ],
  },
  {
    id: "lake_union",
    name: "Lake Union",
    polygon: [
      { lat: 47.655, lng: -122.345 },
      { lat: 47.655, lng: -122.325 },
      { lat: 47.638, lng: -122.325 },
      { lat: 47.638, lng: -122.345 },
    ],
  },
  {
    id: "puget_sound",
    name: "Puget Sound",
    polygon: [
      { lat: 47.80, lng: -122.55 },
      { lat: 47.80, lng: -122.42 },
      { lat: 47.65, lng: -122.42 },
      { lat: 47.55, lng: -122.46 },
      { lat: 47.40, lng: -122.52 },
      { lat: 47.40, lng: -122.65 },
      { lat: 47.65, lng: -122.65 },
    ],
  },
];
