"use client";

import { useState } from "react";

async function post(path, body) {
  const res = await fetch("/api/auth/" + path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const err = new Error(data.detail || data.error || "Something went wrong, please try again.");
    err.status = res.status;
    throw err;
  }
  return data;
}

const TABS = [
  ["signin", "Sign in"],
  ["signup", "Sign up"],
];

// Two screens, no password anywhere:
//  - Sign in : your email -> a one-time link by email
//  - Sign up : your name and email -> a confirmation link by email that creates the account and signs you in
export default function Login({ message, initialMode = "signin" }) {
  const [mode, setMode] = useState(initialMode);
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  const [suggest, setSuggest] = useState(""); // the other screen to offer after a "no account" / "already exists" error

  function switchTo(next) {
    setMode(next);
    setError("");
    setNotice("");
    setSuggest("");
  }

  async function submit(e) {
    e.preventDefault();
    setError("");
    setNotice("");
    setSuggest("");
    setBusy(true);
    try {
      if (mode === "signin") {
        await post("demande", { email });
        setNotice(`Link sent to ${email}!  It expires in 15 minutes and works once.`);
      } else {
        await post("inscription", { name, email });
        setNotice(`Almost done! We sent a confirmation link to ${email}. Open it to create your account and sign in (check your spam folder too). It expires in 15 minutes.`);
      }
    } catch (err) {
      setError(err.message);
      if (mode === "signin" && err.status === 404) setSuggest("signup");
      if (mode === "signup" && err.status === 409) setSuggest("signin");
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <header className="entete">
        <h1 className="titre">QA System — Historical Mysteries</h1>
        <p className="sous-titre">Ask history questions and get answers with their sources.</p>
        <p className="ornement">· · ·</p>
      </header>
      <form className="login auth" onSubmit={submit}>
        <div className="auth-tabs" role="tablist" aria-label="Account">
          {TABS.map(([id, label]) => (
            <button key={id} type="button" role="tab" aria-selected={mode === id} className={"auth-tab" + (mode === id ? " on" : "")} onClick={() => switchTo(id)}>
              {label}
            </button>
          ))}
        </div>
        <h2>{mode === "signup" ? "Create your account" : "Welcome back"}</h2>
        <p>
          {mode === "signup"
            ? "Tell us your name and email. We send you a confirmation link: no password to create."
            : "Enter your email and we send you a one-time sign-in link: no password to remember."}
        </p>
        {message && !error && <p className="erreur">{message}</p>}

        {mode === "signup" && (
          <div className="auth-field">
            <label htmlFor="auth-name">Name</label>
            <input id="auth-name" type="text" required minLength={2} maxLength={60} autoComplete="name" placeholder="Your name" value={name} onChange={(e) => setName(e.target.value)} />
          </div>
        )}
        <div className="auth-field">
          <label htmlFor="auth-email">Email</label>
          <input id="auth-email" type="email" required autoComplete="email"  value={email} onChange={(e) => setEmail(e.target.value)} />
        </div>

        <button type="submit" disabled={busy}>
          {busy ? "Sending..." : mode === "signup" ? "Create my account" : "Send me a sign-in link"}
        </button>

        {notice && <p className="succes">{notice}</p>}
        {error && <p className="erreur">{error}</p>}
        {suggest && (
          <button type="button" className="auth-link" onClick={() => switchTo(suggest)}>
            {suggest === "signup" ? "Create an account instead" : "Go to Sign in"}
          </button>
        )}

        <div className="auth-switch">
          {mode === "signin" ? (
            <p>
              No account yet?{" "}
              <button type="button" className="auth-link" onClick={() => switchTo("signup")}>
                Sign up
              </button>
            </p>
          ) : (
            <p>
              Already have an account?{" "}
              <button type="button" className="auth-link" onClick={() => switchTo("signin")}>
                Sign in
              </button>
            </p>
          )}
        </div>
      </form>
    </>
  );
}
