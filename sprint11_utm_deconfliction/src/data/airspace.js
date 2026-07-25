// Separation & detect-and-avoid parameters.
//
// HONESTY NOTE — READ THIS. There is no ratified separation minimum for
// low-altitude UAM/UTM traffic. FAA UTM ConOps v2.0 and ASTM F3548-21 define
// STRATEGIC deconfliction through shared 4D "operational intents" / operational
// volumes with a containment buffer, not a single point-to-point minimum.
// RTCA DO-365 (SC-228) defines a TACTICAL "DAA Well Clear" (DWC) for larger UAS
// integrating with manned traffic: HMD 4000 ft (~1219 m), vertical 450 ft
// (~137 m), modified-tau 35 s. Those values are far too large for slow urban
// eVTOL corridors, so the defaults below are ILLUSTRATIVE values in the range
// discussed in NASA UAM and EASA corridor studies. Every one is user-editable
// in the UI; none should be read as a regulatory minimum.

export const SEP = {
  // Strategic (pre-departure, 4D intent) protected volume.
  strat_horiz_m: 300,   // horizontal buffer around a 4D trajectory (corridor-scale)
  strat_vert_m: 30,     // vertical buffer (also the altitude-layer spacing)

  // Tactical (in-flight) DAA "well clear" thresholds (DO-365 formulation,
  // scaled to urban eVTOL speeds).
  daa_hmd_m: 150,       // horizontal miss distance threshold
  daa_vert_m: 30,       // vertical separation threshold
  daa_tau_s: 25,        // modified time-to-CPA threshold

  // Loss-of-separation (LoS) hard floor — a genuine near-miss if breached.
  los_horiz_m: 60,
  los_vert_m: 15,
};

// Cruise altitude layers (m AGL). Strategic deconfliction assigns vehicles to
// layers spaced by strat_vert_m so climb/descent legs are the only vertical
// conflict risk. Values are illustrative UAM corridor bands.
export const ALT_LAYERS = [300, 330, 360, 390, 420, 450];

// Vertiport pad throughput. A pad can only launch one operation every
// `service_s`; concurrent demand at a hub therefore queues into departure
// delays. Vertiport pad throughput is the constraint most widely cited (NASA
// UAM, EASA, Uber Elevate) as the binding limit on UAM network capacity — so
// it, not free-airspace conflicts, is what saturates the network here.
// 90 s is a mid-range launch/recovery pad-occupancy figure from those studies.
export const PAD = { service_s: 90 };
