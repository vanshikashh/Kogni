"use client";
import { useState, useRef, useEffect } from "react";
import { LiveScore } from "@/types/kogni";
import { fetchPassage, measureRecovery } from "@/lib/api";

interface Props {
  intervention: LiveScore;
  onDismiss: () => void;
}

export function RecoveryModal({ intervention, onDismiss }: Props) {
  const [passage, setPassage]     = useState("Loading passage...");
  const [passageId, setPassageId] = useState(0);
  const [typed, setTyped]         = useState("");
  const [timings, setTimings]     = useState<number[]>([]);
  const [result, setResult]       = useState<null | {
    recovered: boolean; message: string; post_iki_mean: number;
  }>(null);
  const [loading, setLoading]     = useState(false);

  useEffect(() => {
    fetchPassage()
      .then(p => { setPassage(p.text); setPassageId(p.passage_id); })
      .catch(() => setPassage(
        "The system monitors keystroke timing to infer cognitive load. Type steadily at your natural pace."
      ));
  }, []);

  function handleKeyDown() {
    setTimings(prev => [...prev, Date.now()]);
  }

  async function handleSubmit() {
    setLoading(true);
    try {
      const res = await measureRecovery(timings, intervention.fatigue_score, passageId);
      setResult({ recovered: res.recovered, message: res.message, post_iki_mean: res.post_iki_mean });
    } catch {
      setResult({ recovered: false, message: "Measurement failed — try again.", post_iki_mean: 0 });
    } finally {
      setLoading(false);
    }
  }

  const pct = Math.min(100, Math.round((typed.length / passage.length) * 100));

  return (
    <div style={{
      position:"fixed", inset:0,
      background:"rgba(0,0,0,.7)", backdropFilter:"blur(4px)",
      display:"flex", alignItems:"center", justifyContent:"center",
      zIndex:9000,
    }}>
      <div style={{
        background:"#fff", border:"3px solid #000",
        boxShadow:"6px 6px 0 #000",
        width:"min(480px,95vw)", overflow:"hidden",
      }}>
        <div style={{
          background:"linear-gradient(180deg,#1a6fe8,#0055CC)",
          padding:"5px 8px", display:"flex",
          alignItems:"center", justifyContent:"space-between",
          borderBottom:"2px solid #000",
        }}>
          <span style={{ fontFamily:"'Press Start 2P',monospace", fontSize:6.5, color:"#fff" }}>
            ⚡ RECOVERY TASK
          </span>
          <button onClick={onDismiss} style={{
            width:16, height:16, background:"#E8212C",
            border:"2px solid #000", color:"#fff",
            fontFamily:"'Press Start 2P',monospace", fontSize:7, cursor:"pointer",
          }}>×</button>
        </div>

        <div style={{ padding:16 }}>
          {!result ? (
            <>
              <div style={{
                fontFamily:"'Press Start 2P',monospace", fontSize:6,
                color:"#888", marginBottom:8,
              }}>TYPE NATURALLY — WE MEASURE RHYTHM, NOT SPEED</div>

              <div style={{
                background:"#f8f9ff", border:"2px solid #000",
                padding:10, marginBottom:10,
                fontFamily:"'Nunito',sans-serif", fontSize:14,
                lineHeight:1.7, color:"#333",
              }}>{passage}</div>

              <textarea
                value={typed}
                onChange={e => setTyped(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="Start typing here..."
                style={{
                  width:"100%", height:72, border:"3px solid #000",
                  padding:8, fontFamily:"'Nunito',sans-serif",
                  fontSize:14, resize:"none", outline:"none",
                }}
              />

              <div style={{
                height:8, background:"#eee", border:"2px solid #000",
                margin:"8px 0", overflow:"hidden",
              }}>
                <div style={{
                  width:`${pct}%`, height:"100%",
                  background:"linear-gradient(90deg,#0055CC,#1a6fe8)",
                  transition:"width .2s ease",
                }} />
              </div>

              <div style={{
                fontFamily:"'Press Start 2P',monospace",
                fontSize:6, color:"#888", marginBottom:10,
              }}>{pct}% — KEYSTROKES CAPTURED: {timings.length}</div>

              <div style={{ display:"flex", gap:6 }}>
                <button
                  onClick={handleSubmit}
                  disabled={pct < 40 || loading}
                  style={{
                    flex:2,
                    background: pct >= 40 ? "linear-gradient(180deg,#3d8c2c,#2a6a1c)" : "#ccc",
                    color:"#fff", border:"2px solid #000",
                    boxShadow:"2px 2px 0 #000", padding:"8px 0",
                    fontFamily:"'Press Start 2P',monospace", fontSize:6,
                    cursor: pct >= 40 ? "pointer" : "not-allowed",
                  }}
                >{loading ? "MEASURING..." : "▶ SUBMIT & MEASURE"}</button>
                <button onClick={onDismiss} style={{
                  flex:1, background:"#fff", border:"2px solid #000",
                  boxShadow:"2px 2px 0 #000", padding:"8px 0",
                  fontFamily:"'Press Start 2P',monospace", fontSize:6, cursor:"pointer",
                }}>SKIP</button>
              </div>
            </>
          ) : (
            <div style={{ textAlign:"center", padding:"24px 0" }}>
              <div style={{ fontSize:48, marginBottom:8 }}>{result.recovered ? "✓" : "~"}</div>
              <div style={{
                fontFamily:"'Press Start 2P',monospace", fontSize:8,
                color: result.recovered ? "#3CB043" : "#FF8C00",
                marginBottom:8,
              }}>
                {result.recovered ? "RHYTHM RESTORED" : "PARTIALLY RECOVERED"}
              </div>
              <div style={{
                fontFamily:"'Nunito',sans-serif", fontSize:13,
                color:"#555", marginBottom:12,
              }}>{result.message}</div>
              {result.post_iki_mean > 0 && (
                <div style={{
                  fontFamily:"'Press Start 2P',monospace", fontSize:6,
                  color:"#0055CC", background:"#e8f0fe",
                  border:"1px solid #c5d5f8", padding:"4px 8px",
                  display:"inline-block", marginBottom:12,
                }}>POST IKI: {result.post_iki_mean}ms</div>
              )}
              <button onClick={onDismiss} style={{
                display:"block", width:"100%",
                background:"linear-gradient(180deg,#1a6fe8,#0055CC)",
                color:"#fff", border:"2px solid #000",
                boxShadow:"2px 2px 0 #000", padding:"10px 0",
                fontFamily:"'Press Start 2P',monospace", fontSize:6,
                cursor:"pointer",
              }}>CLOSE</button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
