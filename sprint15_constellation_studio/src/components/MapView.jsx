import { MapContainer, TileLayer, CircleMarker, Polygon, Marker, Tooltip } from "react-leaflet";
import L from "leaflet";
import { D2R, R2D } from "../data/constants.js";

// Destination point on a sphere given start, bearing and angular distance.
function destPoint(lat1d, lon1d, brg_rad, ang_rad) {
  const lat1 = lat1d * D2R, lon1 = lon1d * D2R;
  const lat2 = Math.asin(
    Math.sin(lat1) * Math.cos(ang_rad) + Math.cos(lat1) * Math.sin(ang_rad) * Math.cos(brg_rad)
  );
  const lon2 =
    lon1 +
    Math.atan2(
      Math.sin(brg_rad) * Math.sin(ang_rad) * Math.cos(lat1),
      Math.cos(ang_rad) - Math.sin(lat1) * Math.sin(lat2)
    );
  return [lat2 * R2D, lon2 * R2D];
}

// Footprint boundary as a lat/lng polygon. Handles the two hard cases:
//  - the circle encloses a pole  -> emit the "cap" as a band closed over the pole
//  - the circle crosses the dateline -> unwrap longitudes so it stays continuous
export function footprintPolygon(lat, lon, ang_rad, steps = 48) {
  const enclosesPole = Math.abs(lat) + ang_rad * R2D >= 90;
  const pts = [];
  for (let k = 0; k <= steps; k++) pts.push(destPoint(lat, lon, (k / steps) * 2 * Math.PI, ang_rad));

  if (enclosesPole) {
    const poleLat = lat >= 0 ? 90 : -90;
    const sorted = pts
      .map(([la, lo]) => [la, ((((lo + 180) % 360) + 360) % 360) - 180])
      .sort((a, b) => a[1] - b[1]);
    return [[poleLat, -180], ...sorted, [poleLat, 180]];
  }

  // unwrap longitudes for dateline continuity
  const out = [pts[0]];
  for (let k = 1; k < pts.length; k++) {
    let [la, lo] = pts[k];
    const prev = out[k - 1][1];
    while (lo - prev > 180) lo -= 360;
    while (lo - prev < -180) lo += 360;
    out.push([la, lo]);
  }
  return out;
}

export default function MapView({ subPoints, halfAngle, site, showFootprints, color }) {
  return (
    <MapContainer
      center={[20, 0]}
      zoom={2}
      minZoom={2}
      maxZoom={6}
      worldCopyJump={false}
      style={{ height: "100%", width: "100%", background: "#050914" }}
      preferCanvas={true}
    >
      <TileLayer
        url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
        attribution="&copy; OpenStreetMap &copy; CARTO"
        noWrap={true}
      />

      {/* coverage footprints — translucent, they merge into a coverage blanket */}
      {showFootprints &&
        subPoints.map((sp) => (
          <Polygon
            key={`f${sp.id}`}
            positions={footprintPolygon(sp.lat, sp.lon, halfAngle)}
            pathOptions={{ color, weight: 0, fillColor: color, fillOpacity: 0.13 }}
          />
        ))}

      {/* satellites */}
      {subPoints.map((sp) => (
        <CircleMarker
          key={`s${sp.id}`}
          center={[sp.lat, sp.lon]}
          radius={2.5}
          pathOptions={{ color, weight: 0, fillColor: color, fillOpacity: 0.95 }}
        />
      ))}

      {/* ground site */}
      <Marker
        position={[site.lat, site.lng]}
        icon={L.divIcon({
          className: "site-icon",
          html: `<div class="site-dot"></div>`,
          iconSize: [12, 12],
          iconAnchor: [6, 6],
        })}
      >
        <Tooltip direction="top">{site.name}</Tooltip>
      </Marker>
    </MapContainer>
  );
}
