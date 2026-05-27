"use client";
import { useState, useEffect } from "react";
import { clearToken } from "@/lib/api";
import { LoginPage } from "@/components/LoginPage";
import { DashboardPage } from "@/components/DashboardPage";

export default function Home() {
  const [authed, setAuthed] = useState(false);
  const [ready, setReady]   = useState(false);

  useEffect(() => {
    const token = localStorage.getItem("kogni_token");
    setAuthed(!!token && token.length > 20);
    setReady(true);

    // Re-check token on focus (handles tab switching)
    const onFocus = () => {
      const t = localStorage.getItem("kogni_token");
      if (!t || t.length < 20) setAuthed(false);
    };
    window.addEventListener("focus", onFocus);
    return () => window.removeEventListener("focus", onFocus);
  }, []);

  // Also check every 30 seconds in case token changes
  useEffect(() => {
    if (!ready) return;
    const interval = setInterval(() => {
      const token = localStorage.getItem("kogni_token");
      setAuthed(!!token && token.length > 20);
    }, 30000);
    return () => clearInterval(interval);
  }, [ready]);

  if (!ready) return null;

  if (!authed) {
    return <LoginPage onAuth={() => setAuthed(true)} />;
  }

  return (
    <DashboardPage onLogout={() => {
      clearToken();
      setAuthed(false);
    }} />
  );
}
