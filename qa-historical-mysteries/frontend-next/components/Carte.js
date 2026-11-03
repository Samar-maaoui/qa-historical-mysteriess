"use client";

import "leaflet/dist/leaflet.css";
import { MapContainer, TileLayer, CircleMarker, Tooltip } from "react-leaflet";

export default function Carte({ lieux }) {
  const un = lieux.length === 1;
  const lats = lieux.map((l) => l.lat);
  const lons = lieux.map((l) => l.lon);
  const props = un
    ? { center: [lieux[0].lat, lieux[0].lon], zoom: 6 }
    : {
        bounds: [[Math.min(...lats), Math.min(...lons)], [Math.max(...lats), Math.max(...lons)]],
        boundsOptions: { padding: [40, 40] },
      };
  return (
    <MapContainer {...props} scrollWheelZoom={false} style={{ height: 300, width: "100%" }}>
      <TileLayer
  attribution="&copy; contributeurs d'OpenStreetMap"
  url="https://tile.openstreetmap.org/{z}/{x}/{y}.png"
/>
      {lieux.map((l) => (
        <CircleMarker
          key={l.titre}
          center={[l.lat, l.lon]}
          radius={9}
          pathOptions={{ color: "#6b4423", fillColor: "#b08d57", fillOpacity: 0.9 }}
        >
<Tooltip direction="top">{l.nom}</Tooltip>    </CircleMarker>
      ))}
    </MapContainer>
  );
}