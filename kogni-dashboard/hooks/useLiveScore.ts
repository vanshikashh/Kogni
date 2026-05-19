"use client";
import { useEffect, useRef, useState, useCallback } from "react";
import { createLiveSocket, getToken } from "@/lib/api";
import { LiveScore } from "@/types/kogni";

export function useLiveScore() {
  const [liveScore, setLiveScore]           = useState<LiveScore | null>(null);
  const [intervention, setIntervention]     = useState<LiveScore | null>(null);
  const [connected, setConnected]           = useState(false);
  const wsRef = useRef<WebSocket | null>(null);

  const connect = useCallback(() => {
    const token = getToken();
    if (!token) return;

    wsRef.current?.close();

    const ws = createLiveSocket(
      token,
      (data) => {
        const msg = data as LiveScore;
        if (msg.type === "recovery_intervention") {
          setIntervention(msg);
        } else {
          setLiveScore(msg);
        }
        setConnected(true);
      },
      () => {
        setConnected(false);
        // Auto-reconnect after 5s
        setTimeout(connect, 5000);
      }
    );

    wsRef.current = ws;
  }, []);

  useEffect(() => {
    connect();
    return () => wsRef.current?.close();
  }, [connect]);

  const dismissIntervention = () => setIntervention(null);

  return { liveScore, intervention, connected, dismissIntervention };
}
