"use client";

import "leaflet/dist/leaflet.css";
import { useEffect, useMemo } from "react";
import { CircleMarker, MapContainer, Popup, TileLayer, Tooltip, useMap } from "react-leaflet";
import { eraColor } from "@/lib/eras";

function Fit({ points }) {
  const map = useMap();
  useEffect(() => {
    if (!points.length) return;
    if (points.length === 1) map.setView(points[0], 6);
    else map.fitBounds(points, { padding: [40, 40], maxZoom: 7 });
  }, [points, map]);
  return null;
}

export default function MapView({ sites, onAsk }) {
  const points = useMemo(() => sites.map((s) => [s.lat, s.lon]), [sites]);
  return (
    <MapContainer center={[25, 15]} zoom={2} scrollWheelZoom style={{ height: 460, width: "100%" }}>
      <TileLayer attribution="&copy; contributeurs d'OpenStreetMap" url="https://tile.openstreetmap.org/{z}/{x}/{y}.png" />
      <Fit points={points} />
      {sites.map((s) => (
        <CircleMarker key={s.titre} center={[s.lat, s.lon]} radius={s.kind === "site" ? 9 : 6} pathOptions={{ color: "#4a3728", weight: 1.5, fillColor: eraColor(s.era), fillOpacity: s.kind === "site" ? 0.95 : 0.6 }}>
          <Tooltip direction="top">{s.nom}</Tooltip>
          <Popup>
            <strong>
              {s.nom}
            </strong>
            <br />
            {s.era} · {s.year}
            <br />
            <em>{s.kind === "site" ? "Archaeological or historical site" : "Place linked to this topic"}</em>
            <br />
            <button type="button" className="mini" onClick={() => onAsk(`Tell me about ${s.nom}`)}>
              Ask about this
            </button>
          </Popup>
        </CircleMarker>
      ))}
    </MapContainer>
  );
}
