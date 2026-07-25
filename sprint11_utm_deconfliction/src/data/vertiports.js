// Vertiport / operating-site networks, grouped by region.
//
// HONESTY NOTE: these are real airports, heliports and studied UAM sites.
// Coordinates are approximate site centroids. Their use here as connected
// on-demand networks is ILLUSTRATIVE — no real scheduled service links them,
// and nothing here represents an approved commercial route.
//
// Sources:
//  - Paris: Groupe ADP / RATP "Re.Invent Air Mobility" programme
//    (Pontoise-Cormeilles vertiport, Austerlitz Seine barge, Saint-Cyr,
//    Versailles, Le Bourget, Issy heliport) around the 2024 Games.
//  - Dallas–Fort Worth: Uber Elevate's launch market; sites reflect the
//    DFW metroplex airports and skyport locations discussed publicly
//    (DFW Intl, Love Field, Las Colinas/Irving, Frisco Station, Fort Worth
//    Alliance, Arlington, Plano Legacy, Addison, McKinney).

export const REGIONS = {
  paris: {
    id: "paris",
    name: "Paris (Groupe ADP network)",
    ref: { lat: 48.8566, lng: 2.3522 },
    center: [48.86, 2.35],
    zoom: 10,
    vertiports: [
      { id: "austerlitz", name: "Austerlitz Barge (Seine)", lat: 48.8420, lng: 2.3660, kind: "vertiport" },
      { id: "issy",       name: "Issy-les-Moulineaux Heliport", lat: 48.8330, lng: 2.2730, kind: "heliport" },
      { id: "lebourget",  name: "Paris–Le Bourget", lat: 48.9694, lng: 2.4414, kind: "airport" },
      { id: "pontoise",   name: "Pontoise–Cormeilles Vertiport", lat: 49.0966, lng: 2.0408, kind: "vertiport" },
      { id: "saintcyr",   name: "Saint-Cyr-l'École", lat: 48.8106, lng: 2.0747, kind: "airfield" },
      { id: "versailles", name: "Versailles Satory", lat: 48.7930, lng: 2.1240, kind: "vertiport" },
      { id: "cdg",        name: "Paris–Charles-de-Gaulle", lat: 49.0097, lng: 2.5479, kind: "airport" },
      { id: "orly",       name: "Paris–Orly", lat: 48.7233, lng: 2.3794, kind: "airport" },
      { id: "ladefense",  name: "La Défense", lat: 48.8920, lng: 2.2380, kind: "vertiport" },
      { id: "disney",     name: "Marne-la-Vallée", lat: 48.8720, lng: 2.7830, kind: "vertiport" },
    ],
  },

  dallas: {
    id: "dallas",
    name: "Dallas–Fort Worth (Uber Elevate market)",
    ref: { lat: 32.85, lng: -97.04 },
    center: [32.85, -97.04],
    zoom: 9,
    vertiports: [
      { id: "dfw",       name: "DFW International", lat: 32.8998, lng: -97.0403, kind: "airport" },
      { id: "dal",       name: "Dallas Love Field", lat: 32.8471, lng: -96.8518, kind: "airport" },
      { id: "downtown",  name: "Downtown Dallas (CBD)", lat: 32.7767, lng: -96.7970, kind: "vertiport" },
      { id: "lascolinas",name: "Las Colinas / Irving", lat: 32.8748, lng: -96.9403, kind: "vertiport" },
      { id: "frisco",    name: "Frisco Station", lat: 33.1000, lng: -96.8360, kind: "vertiport" },
      { id: "ftworth",   name: "Fort Worth Downtown", lat: 32.7555, lng: -97.3308, kind: "vertiport" },
      { id: "alliance",  name: "Fort Worth Alliance", lat: 32.9874, lng: -97.3188, kind: "airport" },
      { id: "arlington", name: "Arlington (Stadiums)", lat: 32.7473, lng: -97.0945, kind: "vertiport" },
      { id: "plano",     name: "Plano Legacy West", lat: 33.0790, lng: -96.8230, kind: "vertiport" },
      { id: "addison",   name: "Addison Airport", lat: 32.9686, lng: -96.8364, kind: "airport" },
    ],
  },
};

// Default region kept as plain exports for backward compatibility (verify.mjs).
export const DEFAULT_REGION = "paris";
export const REF = REGIONS[DEFAULT_REGION].ref;
export const VERTIPORTS = REGIONS[DEFAULT_REGION].vertiports;
export const VERTIPORT_BY_ID = Object.fromEntries(VERTIPORTS.map((v) => [v.id, v]));
