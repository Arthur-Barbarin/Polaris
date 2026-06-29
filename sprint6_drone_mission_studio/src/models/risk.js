// Population exposure model (operational risk proxy).
//
// Real systems use rasterized population density (WorldPop, GHS-POP, LandScan)
// or licensed risk APIs (e.g., Iris Automation, Airspace Link). To keep this
// tool self-contained and demo-ready, we model density as a sum of Gaussian
// "city centers" with published peak intensities and characteristic radii.
// The classification thresholds are inspired by ASTM F3178 Operational Risk
// classes (Desolate / Sparse / Populated / Dense urban).
//
// To plug in a real density grid later: replace popDensity() with a lookup
// against a Cloud-Optimised GeoTIFF or tile service. The downstream API
// (mean/peak class label) is unchanged.

const POP_CENTERS = [
  // (lat, lng, peak intensity 0–10, sigma in km)
  { lat: 47.6062, lng: -122.3321, peak: 8.0, sigma_km: 4.0 }, // Seattle downtown
  { lat: 47.6101, lng: -122.2015, peak: 6.5, sigma_km: 3.0 }, // Bellevue
  { lat: 47.4502, lng: -122.3088, peak: 4.0, sigma_km: 2.5 }, // SeaTac area
];

function haversine_km(a, b) {
  const R = 6371;
  const dLat = ((b.lat - a.lat) * Math.PI) / 180;
  const dLng = ((b.lng - a.lng) * Math.PI) / 180;
  const x =
    Math.sin(dLat / 2) ** 2 +
    Math.cos((a.lat * Math.PI) / 180) *
      Math.cos((b.lat * Math.PI) / 180) *
      Math.sin(dLng / 2) ** 2;
  return 2 * R * Math.asin(Math.sqrt(x));
}

export function popDensity(point) {
  let d = 0.3; // background (rural)
  for (const c of POP_CENTERS) {
    const r = haversine_km(point, c);
    d += c.peak * Math.exp(-(r * r) / (2 * c.sigma_km * c.sigma_km));
  }
  return Math.min(10, d);
}

export function classifyDensity(peak) {
  if (peak < 1) return "Desolate";
  if (peak < 3) return "Sparse";
  if (peak < 6) return "Populated";
  return "Dense urban";
}

export function riskExposure(pathLatLng) {
  if (pathLatLng.length < 2) {
    return { mean: 0, peak: 0, class: "Desolate" };
  }
  let sum = 0;
  let peak = 0;
  for (const p of pathLatLng) {
    const d = popDensity(p);
    sum += d;
    peak = Math.max(peak, d);
  }
  const mean = sum / pathLatLng.length;
  return { mean, peak, class: classifyDensity(peak) };
}
