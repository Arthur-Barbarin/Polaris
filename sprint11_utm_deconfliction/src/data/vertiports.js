// Paris-region vertiport / operating-site network.
//
// HONESTY NOTE: These are real airports, heliports and the Seine barge site
// that were studied or used for the RATP/Groupe ADP + Volocopter Paris UAM
// trials around the 2024 Olympics ("Re.Invent Air Mobility"). Coordinates are
// approximate site centroids. Their use here as a connected on-demand network
// is ILLUSTRATIVE — no real scheduled service links all of them, and nothing
// here represents an approved commercial route.
//
// Sources:
//  - Groupe ADP / RATP "Re.Invent Air Mobility" programme (Pontoise-Cormeilles
//    test vertiport; Austerlitz barge on the Seine; Saint-Cyr; Versailles;
//    Le Bourget; Issy-les-Moulineaux heliport).
//  - Publicly reported 2024 Paris eVTOL demonstration sites.

export const REF = { lat: 48.8566, lng: 2.3522 }; // Paris centre — local ENU origin

export const VERTIPORTS = [
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
];

export const VERTIPORT_BY_ID = Object.fromEntries(VERTIPORTS.map((v) => [v.id, v]));
