"use client";

import "leaflet/dist/leaflet.css";
import { CircleMarker, MapContainer, Polyline, TileLayer, Tooltip, useMapEvents } from "react-leaflet";

function Clicks({ disabled, onGuess }) {
  useMapEvents({
    click(e) {
      if (!disabled) onGuess([e.latlng.lat, e.latlng.lng]);
    },
  });
  return null;
}

export default function WhereMap({ guess, answer, onGuess }) {
  return (
    <MapContainer center={[25, 10]} zoom={2} minZoom={2} worldCopyJump scrollWheelZoom style={{ height: 380, width: "100%" }}>
      <TileLayer attribution="&copy; contributeurs d'OpenStreetMap" url="https://tile.openstreetmap.org/{z}/{x}/{y}.png" />
      <Clicks disabled={Boolean(answer)} onGuess={onGuess} />
      {guess && (
        <CircleMarker center={guess} radius={11} pathOptions={{ color: "#c2410c", fillColor: "#fb923c", fillOpacity: 0.9, weight: 3 }}>
          <Tooltip permanent direction="top">
            You
          </Tooltip>
        </CircleMarker>
      )}
      {answer && (
        <>
          <CircleMarker center={[answer.lat, answer.lon]} radius={12} pathOptions={{ color: "#15803d", fillColor: "#4ade80", fillOpacity: 0.95, weight: 3 }}>
            <Tooltip permanent direction="top">
              {answer.emoji} {answer.nom}
            </Tooltip>
          </CircleMarker>
          {guess && <Polyline positions={[guess, [answer.lat, answer.lon]]} pathOptions={{ color: "#6b4423", dashArray: "6 8", weight: 3 }} />}
        </>
      )}
    </MapContainer>
  );
}
