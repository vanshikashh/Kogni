"use client";
import { useState } from "react";

interface Props { onAuth: () => void; }

const API = "http://localhost:8000";

export function LoginPage({ onAuth }: Props) {
  const [email, setEmail]       = useState("");
  const [password, setPassword] = useState("");
  const [mode, setMode]         = useState<"login" | "register">("login");
  const [loading, setLoading]   = useState(false);
  const [error, setError]       = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);

    const endpoint = mode === "login"
      ? `${API}/api/v1/auth/login`
      : `${API}/api/v1/auth/register`;

    try {
      const res = await fetch(endpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
      });

      const data = await res.json();

      if (!res.ok) {
        setError(data.detail ?? `Error ${res.status}`);
        return;
      }

      if (!data.access_token) {
        setError("No token received from server");
        return;
      }

      // Save token
      localStorage.setItem("kogni_token", data.access_token);
      onAuth();

    } catch (err) {
      setError("Cannot reach API — is uvicorn running on port 8000?");
    } finally {
      setLoading(false);
    }
  }

  const inputStyle: React.CSSProperties = {
    width: "100%",
    border: "3px solid #000",
    padding: "10px 12px",
    fontFamily: "'VT323', monospace",
    fontSize: 22,
    outline: "none",
    background: "#fff",
    marginBottom: 8,
    boxShadow: "inset 2px 2px 0 rgba(0,0,0,.08)",
  };

  return (
    <div style={{
      minHeight: "100vh",
      background: "linear-gradient(180deg,#87CEEB 0%,#b8e4f9 44%,#a8d8a8 44%,#5aad50 100%)",
      display: "flex", alignItems: "center", justifyContent: "center",
    }}>
      <div style={{
        background: "#fff",
        border: "3px solid #000",
        boxShadow: "6px 6px 0 #000",
        width: "min(400px, 94vw)",
        overflow: "hidden",
      }}>
        {/* Title bar */}
        <div style={{
          background: "linear-gradient(180deg,#1a6fe8,#0055CC)",
          padding: "5px 8px",
          display: "flex", alignItems: "center", gap: 8,
          borderBottom: "2px solid #000",
        }}>
          <span style={{ fontSize: 16 }}>🧠</span>
          <span style={{ fontFamily: "'Press Start 2P', monospace", fontSize: 7, color: "#fff" }}>
            KOGNI.EXE — {mode === "login" ? "LOGIN" : "REGISTER"}
          </span>
          <div style={{ marginLeft: "auto", display: "flex", gap: 3 }}>
            {["#FFE600","#3CB043","#E8212C"].map((c,i) => (
              <div key={i} style={{ width: 14, height: 14, background: c, border: "2px solid #000" }} />
            ))}
          </div>
        </div>

        <form onSubmit={handleSubmit} style={{ padding: 20 }}>
          <div style={{
            fontFamily: "'Press Start 2P', monospace",
            fontSize: 6, color: "#888", marginBottom: 14,
          }}>
            COGNITIVE HEALTH MONITOR v0.1
          </div>

          <input
            type="email"
            value={email}
            onChange={e => setEmail(e.target.value)}
            placeholder="EMAIL ADDRESS"
            required
            style={inputStyle}
          />
          <input
            type="password"
            value={password}
            onChange={e => setPassword(e.target.value)}
            placeholder="PASSWORD"
            required
            style={inputStyle}
          />

          {error && (
            <div style={{
              fontFamily: "'Press Start 2P', monospace",
              fontSize: 6, color: "#E8212C",
              background: "#fff0f0", border: "2px solid #E8212C",
              padding: "6px 10px", marginBottom: 8,
              lineHeight: 1.8,
            }}>{error}</div>
          )}

          <button
            type="submit"
            disabled={loading}
            style={{
              width: "100%",
              background: loading ? "#ccc" : "linear-gradient(180deg,#1a6fe8,#0055CC)",
              color: "#fff",
              border: "2px solid #000",
              boxShadow: "3px 3px 0 #000",
              padding: "10px 0",
              fontFamily: "'Press Start 2P', monospace",
              fontSize: 7,
              cursor: loading ? "not-allowed" : "pointer",
              marginBottom: 8,
            }}
          >
            {loading
              ? "CONNECTING..."
              : mode === "login"
                ? "▶ LOGIN"
                : "▶ CREATE ACCOUNT"}
          </button>

          <div style={{ textAlign: "center" }}>
            <button
              type="button"
              onClick={() => { setMode(mode === "login" ? "register" : "login"); setError(null); }}
              style={{
                background: "none", border: "none",
                fontFamily: "'Press Start 2P', monospace",
                fontSize: 5.5, color: "#0055CC",
                cursor: "pointer", textDecoration: "underline",
              }}
            >
              {mode === "login" ? "CREATE NEW ACCOUNT →" : "← BACK TO LOGIN"}
            </button>
          </div>

          {/* API status indicator */}
          <div style={{
            marginTop: 12,
            fontFamily: "'Press Start 2P', monospace",
            fontSize: 5, color: "#aaa",
            textAlign: "center",
          }}>
            API: {API}
          </div>
        </form>
      </div>
    </div>
  );
}
