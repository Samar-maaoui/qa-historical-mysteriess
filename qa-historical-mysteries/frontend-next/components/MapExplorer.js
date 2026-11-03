"use client";

import { useEffect, useMemo, useState } from "react";
import dynamic from "next/dynamic";
import { api } from "@/lib/api";
import { eraColor } from "@/lib/eras";

const MapView = dynamic(() => import("@/components/MapView"), { ssr: false, loading: () => <p className="chargement">Loading the map…</p> });

export default function MapExplorer({ onAsk }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const [eras, setEras] = useState(null); // null = all
  const [tunisiaOnly, setTunisiaOnly] = useState(false);
  const [withPlaces, setWithPlaces] = useState(true);

  useEffect(() => {
    let cancelled = false;
    api("/sites")
      .then((d) => !cancelled && setData(d))
      .catch((e) => !cancelled && setError(e.message));
    return () => {
      cancelled = true;
    };
  }, []);

  const selected = useMemo(() => eras || data?.eras || [], [eras, data]);
  const visible = useMemo(() => {
    if (!data) return [];
    return data.sites.filter((s) => selected.includes(s.era) && (!tunisiaOnly || s.tunisia) && (withPlaces || s.kind === "site"));
  }, [data, selected, tunisiaOnly, withPlaces]);

  function toggle(era) {
    const base = eras || data.eras;
    setEras(base.includes(era) ? base.filter((e) => e !== era) : [...base, era]);
  }

  if (error) return <p className="erreur">{error}</p>;
  if (!data) return <p className="chargement">Loading the map…</p>;

  return (
    <section className="panel">
      <h2 className="panel-h">Explore the map by era</h2>
      <p className="muted">Filter the places by period, then click a marker to ask about it.</p>
      <div className="filters">
        {data.eras.map((e) => (
          <button key={e} type="button" className={"chip" + (selected.includes(e) ? " on" : "")} onClick={() => toggle(e)} style={selected.includes(e) ? { background: eraColor(e), borderColor: eraColor(e) } : undefined}>
            {e}
          </button>
        ))}
        <label className="check">
          <input type="checkbox" checked={tunisiaOnly} onChange={(e) => setTunisiaOnly(e.target.checked)} /> Tunisia only
        </label>
        <label className="check">
          <input type="checkbox" checked={withPlaces} onChange={(e) => setWithPlaces(e.target.checked)} /> Include linked places
        </label>
      </div>
      <div className="carte big">
        <MapView sites={visible} onAsk={onAsk} />
      </div>
      <p className="muted">
        {visible.length} place{visible.length === 1 ? "" : "s"} shown.
      </p>
      <div className="site-list">
        {visible.map((s) => (
          <button key={s.titre} type="button" className="site-card" onClick={() => onAsk(`Tell me about ${s.nom}`)}>
            <span className="dot" style={{ background: eraColor(s.era) }} />
            <strong>
              {s.nom}
            </strong>
            <span className="muted">
              {s.era} · {s.year}
            </span>
          </button>
        ))}
      </div>
    </section>
  );
}
