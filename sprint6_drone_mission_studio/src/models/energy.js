// Energy & range model.
//
// Approach: derive average mission power empirically from advertised endurance
// (rather than inventing a physics model from rotor geometry that an operator
// will distrust). Result is anchored to manufacturer-quoted flight time, with
// a 15% reserve applied per common FAA / industry practice (≥20–25% recommended
// for BVLOS; we use 15% as a baseline that the operator can tighten).
//
// Formula:
//   P_avg [W]   = battery_Wh × USABLE_FRACTION / (t_max_h)
//   E_mission   = P_avg × (cruise_time + hover_time)
//   t_cruise    = distance / ground_speed
//   ground_speed = max(0, airspeed_cruise − headwind_component)
//
// Sensitivity: P_avg is treated as constant across cruise & hover; this is
// optimistic for hover-heavy missions (real hover power on a quadrotor
// is typically 5–15% above cruise power at best L/D). The constant-P assumption
// is *honest if you state it*, which we do.
//
// For drones with no published battery (Wing, Zipline P2), we fall back to a
// range-based feasibility check: feasible iff one-way distance ≤ published
// range × USABLE_FRACTION. No Wh value is reported in that case.

export const USABLE_BATTERY_FRACTION = 0.85;

export function avgPowerW(drone, payload_kg = 0) {
  // Baseline power = manufacturer endurance at empty MTOW.
  // Adding payload scales hover power as P ∝ W^1.5 (induced power dominates;
  // standard momentum-theory result for a rotor at fixed disk loading).
  if (drone.battery_wh == null) return null;
  const t_h = drone.max_flight_time_min / 60;
  const p0 = (drone.battery_wh * USABLE_BATTERY_FRACTION) / t_h;
  if (payload_kg <= 0) return p0;
  const scale = Math.pow(
    (drone.mtow_kg + payload_kg) / drone.mtow_kg,
    1.5
  );
  return p0 * scale;
}

export function maxRangeM(drone) {
  // Still-air range at cruise speed, with usable-battery derate.
  const t_h = drone.max_flight_time_min / 60;
  return drone.cruise_ms * 3600 * t_h * USABLE_BATTERY_FRACTION;
}

export function effectiveGroundSpeed(drone, headwind_ms) {
  return Math.max(0, drone.cruise_ms - headwind_ms);
}

// Decompose wind into headwind component along the great-circle bearing.
// bearing_deg: 0=N, 90=E. wind_from_deg: meteorological convention (wind
// coming FROM that direction, so 90 = wind from east, blowing toward west).
export function headwindComponent(wind_speed_ms, wind_from_deg, bearing_deg) {
  // wind vector points toward: wind_from + 180
  const wind_to = (wind_from_deg + 180) % 360;
  // Headwind = -|wind|·cos(angle between flight direction and wind-toward)
  const theta = ((bearing_deg - wind_to + 540) % 360) - 180; // signed [-180,180]
  return -wind_speed_ms * Math.cos((theta * Math.PI) / 180);
}

export function pathBearing(a, b) {
  const lat1 = (a.lat * Math.PI) / 180;
  const lat2 = (b.lat * Math.PI) / 180;
  const dLng = ((b.lng - a.lng) * Math.PI) / 180;
  const y = Math.sin(dLng) * Math.cos(lat2);
  const x =
    Math.cos(lat1) * Math.sin(lat2) -
    Math.sin(lat1) * Math.cos(lat2) * Math.cos(dLng);
  return ((Math.atan2(y, x) * 180) / Math.PI + 360) % 360;
}

export function missionEnergy(drone, distance_m, headwind_ms = 0, hover_s = 0, payload_kg = 0) {
  if (drone.cruise_ms <= 0) {
    return { feasible: false, reason: "No cruise speed defined" };
  }
  const gs = effectiveGroundSpeed(drone, headwind_ms);
  if (gs <= 0.5) {
    return {
      feasible: false,
      reason: `Headwind ${headwind_ms.toFixed(1)} m/s ≥ cruise ${drone.cruise_ms} m/s — no forward progress`,
    };
  }
  const t_cruise_s = distance_m / gs;
  const t_total_s = t_cruise_s + hover_s;

  if (drone.battery_wh == null) {
    // Range-based feasibility. Payload scaling derates the published range
    // by the inverse power ratio so heavier loads shrink the usable corridor.
    const payload_derate = payload_kg > 0
      ? Math.pow(drone.mtow_kg / (drone.mtow_kg + payload_kg), 1.5)
      : 1;
    const max_dist = drone.range_km_one_way * 1000 * USABLE_BATTERY_FRACTION * payload_derate;
    const range_used_pct = (distance_m / max_dist) * 100;
    return {
      feasible: range_used_pct <= 100,
      energy_wh: null,
      energy_available_wh: null,
      time_s: t_total_s,
      ground_speed_ms: gs,
      range_used_pct,
      avg_power_w: null,
      note: "Battery capacity not publicly disclosed; feasibility via published range.",
    };
  }

  const P = avgPowerW(drone, payload_kg);
  const E_wh = (P * t_total_s) / 3600;
  const E_avail = drone.battery_wh * USABLE_BATTERY_FRACTION;
  return {
    feasible: E_wh <= E_avail,
    energy_wh: E_wh,
    energy_available_wh: E_avail,
    time_s: t_total_s,
    ground_speed_ms: gs,
    margin_pct: ((E_avail - E_wh) / E_avail) * 100,
    avg_power_w: P,
  };
}
