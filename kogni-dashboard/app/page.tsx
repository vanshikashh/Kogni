"use client";
import { useState, useEffect } from "react";
import { clearToken } from "@/lib/api";
import { LoginPage } from "@/components/LoginPage";
import { DashboardPage } from "@/components/DashboardPage";

export default function Home() {
  const [authed, setAuthed] = useState(false);
  const [ready, setReady]   = useState(false);

  useEffect(() => {
    // Always read fresh from localStorage — never from stale state
    const token = localStorage.getItem("kogni_token");
    setAuthed(!!token && token.length > 10);
    setReady(true);
  }, []);

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
