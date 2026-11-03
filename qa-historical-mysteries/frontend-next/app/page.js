"use client";

import { useEffect, useRef, useState } from "react";
import Admin from "@/components/Admin";
import Compare from "@/components/Compare";
import Explorer from "@/components/Explorer";
import Login from "@/components/Login";
import MapExplorer from "@/components/MapExplorer";
import Notebook from "@/components/Notebook";
import Kids from "@/components/kids/Kids";
import { api } from "@/lib/api";

// No emoji in the interface, except for the door to the Kids section.
const NAV = [
  ["explore", "Explorer"],
  ["compare", "Compare"],
  ["map", "Map"],
  ["notebook", "Notebook"],
  ["kids", "🐘 Kids"],
];

export default function Home() {
  const [me, setMe] = useState(undefined); // undefined = checking, null = signed out, object = signed in
  const [messageAuth, setMessageAuth] = useState("");
  const [view, setView] = useState("explore");
  const [visited, setVisited] = useState({ explore: true });
  const [sujets, setSujets] = useState([]);
  const explorer = useRef(null);
  const checked = useRef(false);

  // 1) on load: token in the URL? otherwise, existing session?
  useEffect(() => {
    if (checked.current) return;
    checked.current = true;
    async function init() {
      const token = new URLSearchParams(window.location.search).get("token");
      if (token) {
        window.history.replaceState({}, "", window.location.pathname);
        try {
          const res = await fetch("/api/auth/verifier", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ token }) });
          const data = await res.json();
          if (res.ok) {
            setMe({ email: data.email, admin: Boolean(data.admin), name: data.name || null });
            return;
          }
          setMessageAuth(data.detail || "Invalid or expired link.");
        } catch (e) {
          setMessageAuth("Server unreachable.");
        }
      }
      try {
        const res = await fetch("/api/auth/moi");
        if (res.ok) {
          const data = await res.json();
          setMe({ email: data.email, admin: Boolean(data.admin), name: data.name || null });
          return;
        }
      } catch (e) {
        // not signed in
      }
      setMe(null);
    }
    init();
  }, []);

  // an API call answered 401 after sign-in: the session ended
  useEffect(() => {
    function expired() {
      setMe(null);
      setMessageAuth("Your session has expired. Please sign in again.");
    }
    window.addEventListener("session-expired", expired);
    return () => window.removeEventListener("session-expired", expired);
  }, []);

  // 2) once signed in: the list of topics (names, eras; emojis are used by the Kids section only)
  useEffect(() => {
    if (!me) return;
    let cancelled = false;
    api("/sujets")
      .then((d) => {
        if (cancelled) return;
        setSujets(d.sujets || []);
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [me]);

  async function deconnexion() {
    try {
      await fetch("/api/auth/deconnexion", { method: "POST" });
    } catch (e) {
      // the cookie is cleared by the server; nothing else to do here
    }
    setMe(null);
    setMessageAuth("");
    setView("explore");
    setVisited({ explore: true });
    setSujets([]);
  }

  function go(id) {
    setView(id);
    setVisited((v) => ({ ...v, [id]: true }));
  }

  // from the map: jump to the Explorer and ask
  function askAbout(question) {
    go("explore");
    explorer.current?.ask(question);
  }

  if (me === undefined) return <p className="chargement" style={{ marginTop: "4rem" }}>Loading…</p>;
  if (!me) return <Login message={messageAuth} />;

  const nav = me.admin ? [...NAV, ["admin", "Admin"]] : NAV;
  const show = (id) => ({ display: view === id ? "block" : "none" });

  return (
    <>
      <nav className="topnav" aria-label="Sections">
        <span className="brand">QA Mysteries</span>
        <div className="nav-tabs">
          {nav.map(([id, label]) => (
            <button key={id} type="button" className={"nav-tab" + (view === id ? " on" : "")} onClick={() => go(id)} aria-current={view === id ? "page" : undefined}>
              {label}
            </button>
          ))}
        </div>
        <div className="nav-user">
          <span title={me.email}>{me.name || me.email}</span>
          <button type="button" className="secondaire mini" onClick={deconnexion}>
            Sign out
          </button>
        </div>
      </nav>

      <div style={show("explore")}>
        <Explorer ref={explorer} sujets={sujets} />
      </div>
      {visited.kids && (
        <div style={show("kids")}>
          <Kids sujets={sujets} />
        </div>
      )}
      {view === "compare" && <Compare />}
      {view === "map" && <MapExplorer onAsk={askAbout} />}
      {view === "notebook" && <Notebook />}
      {view === "admin" && me.admin && <Admin />}
    </>
  );
}
