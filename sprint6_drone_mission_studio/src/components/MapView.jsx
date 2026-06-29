import {
  MapContainer,
  TileLayer,
  Polyline,
  Polygon,
  CircleMarker,
  Tooltip,
  useMapEvents,
} from "react-leaflet";
import "leaflet/dist/leaflet.css";

function ClickHandler({ onClick }) {
  useMapEvents({
    click(e) {
      onClick({ lat: e.latlng.lat, lng: e.latlng.lng });
    },
  });
  return null;
}

export default function MapView({
  start,
  goal,
  path,
  noFlyPolys,
  onMapClick,
}) {
  return (
    <MapContainer
      center={[47.6062, -122.3321]}
      zoom={11}
      style={{ height: "100%", width: "100%" }}
      scrollWheelZoom={true}
    >
      <TileLayer
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
      />
      <ClickHandler onClick={onMapClick} />
      {noFlyPolys.map((nfz) => (
        <Polygon
          key={nfz.id}
          positions={nfz.polygon.map((p) => [p.lat, p.lng])}
          pathOptions={{
            color: nfz.color,
            fillOpacity: 0.18,
            weight: 1.5,
            dashArray: "4 4",
          }}
        >
          <Tooltip>{nfz.name}</Tooltip>
        </Polygon>
      ))}
      {path.length > 1 && (
        <Polyline
          positions={path.map((p) => [p.lat, p.lng])}
          pathOptions={{ color: "#0066ff", weight: 4, opacity: 0.9 }}
        />
      )}
      {start && (
        <CircleMarker
          center={[start.lat, start.lng]}
          radius={9}
          pathOptions={{
            color: "#fff",
            weight: 2,
            fillColor: "#10b981",
            fillOpacity: 1,
          }}
        >
          <Tooltip permanent direction="top" offset={[0, -10]}>
            Start
          </Tooltip>
        </CircleMarker>
      )}
      {goal && (
        <CircleMarker
          center={[goal.lat, goal.lng]}
          radius={9}
          pathOptions={{
            color: "#fff",
            weight: 2,
            fillColor: "#ef4444",
            fillOpacity: 1,
          }}
        >
          <Tooltip permanent direction="top" offset={[0, -10]}>
            Goal
          </Tooltip>
        </CircleMarker>
      )}
    </MapContainer>
  );
}
