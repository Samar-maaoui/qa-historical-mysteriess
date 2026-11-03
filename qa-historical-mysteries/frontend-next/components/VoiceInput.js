"use client";

import { useRef, useState, useSyncExternalStore } from "react";

const subscribe = () => () => {};
const isSupported = () => typeof window !== "undefined" && Boolean(window.SpeechRecognition || window.webkitSpeechRecognition);

// Microphone button (Web Speech API). Hidden when the browser does not support it.
export default function VoiceInput({ onText, lang = "en-US", className = "", kids = false }) {
  const supported = useSyncExternalStore(subscribe, isSupported, () => false);
  const [listening, setListening] = useState(false);
  const recognition = useRef(null);

  if (!supported) return null;

  function toggle() {
    if (listening) {
      recognition.current?.stop();
      return;
    }
    const Ctor = window.SpeechRecognition || window.webkitSpeechRecognition;
    const r = new Ctor();
    r.lang = lang;
    r.interimResults = false;
    r.maxAlternatives = 1;
    r.onresult = (e) => onText(e.results[0][0].transcript);
    r.onend = () => setListening(false);
    r.onerror = () => setListening(false);
    recognition.current = r;
    setListening(true);
    r.start();
  }

  return (
    <button type="button" className={`mic ${listening ? "on" : ""} ${className}`} onClick={toggle} aria-label={listening ? "Stop listening" : "Speak your question"} title={listening ? "Listening… click to stop" : "Speak your question"}>
      {listening ? (kids ? "⏺️" : "Stop") : kids ? "🎤" : "Mic"}
    </button>
  );
}
