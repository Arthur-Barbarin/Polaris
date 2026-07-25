import { MapContainer, TileLayer, CircleMarker, Polyline, Tooltip, Marker } from "react-leaflet";
import L from "leaflet";
import { VERTIPORTS } from "../data/vertiports.js";

const vpIcon = (v) =>
  L.divIcon({
    className: "vp-icon",
    html: `<div class="vp-dot" title="${v.name}"></div>`,
    iconSize: [10, 10],
    iconAnchor: [5, 5],
  });

// small triangle rotated to heading
function aircraftIcon(a) {
  const rot = a.heading || 0;
  const glow = a.maneuvering ? "aircraft-alert" : "";
  return L.divIcon({
    className: "ac-icon",
    html: `<div class="aircraft ${glow}" style="transform:rotate(${rot}deg);color:${a.color}">▲</div>`,
    iconSize: [22, 22],
    iconAnchor: [11, 11],
  });
}

export default function MapView({ vehicles, conflicts, assignments }) {
  return (
    <MapContainer
      center={[48.86, 2.35]}
      zoom={10}
      style={{ height: "100%", width: "100%", background: "#0b1020" }}
      zoomControl={true}
      preferCanvas={true}
    >
      <TileLayer
        url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
        attribution='&copy; OpenStreetMap &copy; CARTO'
      />

      {/* planned cruise legs (faint) */}
      {assignments?.map((asg, k) => (
        <Polyline
          key={`leg${k}`}
          positions={[
            [asg.flight.origin.lat, asg.flight.origin.lng],
            [asg.flight.dest.lat, asg.flight.dest.lng],
          ]}
          pathOptions={{ color: asg.resolved ? "#334155" : "#b91c1c", weight: 1, opacity: 0.35 }}
        />
      ))}

      {/* vertiports */}
      {VERTIPORTS.map((v) => (
        <Marker key={v.id} position={[v.lat, v.lng]} icon={vpIcon(v)}>
          <Tooltip direction="top">{v.name}</Tooltip>
        </Marker>
      ))}

      {/* live conflict CPA lines */}
      {conflicts?.map((c, k) => (
        <Polyline
          key={`c${k}`}
          positions={[
            [c.a.lat, c.a.lng],
            [c.b.lat, c.b.lng],
          ]}
          pathOptions={{ color: "#f43f5e", weight: 2, opacity: 0.9, dashArray: "4 4" }}
        />
      ))}

      {/* aircraft */}
      {vehicles.map((a) => (
        <Marker key={a.id} position={[a.lat, a.lng]} icon={aircraftIcon(a)}>
          <Tooltip direction="right" offset={[8, 0]}>
            {a.name}
            {a.intruder ? " (non-cooperative)" : ""} · {Math.round(a.alt)} m
            {a.maneuvering ? " · AVOIDING" : ""}
          </Tooltip>
        </Marker>
      ))}
    </MapContainer>
  );
}
