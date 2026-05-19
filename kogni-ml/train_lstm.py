"""
Kogni LSTM Trainer — Pure NumPy, no PyTorch
"""

import json
import numpy as np
import joblib
from pathlib import Path
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import accuracy_score
from features import FEATURE_COLS
from lstm_model import KogniLSTMNumpy, sigmoid

MODEL_DIR  = Path("models")
MODEL_DIR.mkdir(exist_ok=True)
SEQ_LEN    = 7
N_FEATURES = len(FEATURE_COLS)
N_HIDDEN   = 32


def generate_sequences(n_users=200, seed=42):
    rng = np.random.default_rng(seed)
    fi  = {f: i for i, f in enumerate(FEATURE_COLS)}
    seqs, labels = [], []
    for _ in range(n_users):
        for label in [0, 1]:
            seq = np.zeros((SEQ_LEN, N_FEATURES))
            bi, bs, bt, be = (rng.uniform(160,240), rng.uniform(250,600),
                              rng.uniform(4,12),    rng.uniform(0.01,0.08))
            for day in range(SEQ_LEN):
                t = day/(SEQ_LEN-1); tr = t if label else 1-t
                seq[day,fi["iki_mean"]]            = bi+tr*80+rng.normal(0,15)
                seq[day,fi["iki_std"]]             = 40+tr*50+rng.normal(0,8)
                seq[day,fi["hold_mean"]]           = 80+tr*30+rng.normal(0,10)
                seq[day,fi["error_rate"]]          = np.clip(be+tr*0.12,0,0.5)
                seq[day,fi["key_count"]]           = max(5,100-tr*60+rng.normal(0,10))
                seq[day,fi["scroll_velocity"]]     = bs+tr*500+rng.normal(0,80)
                seq[day,fi["direction_reversals"]] = max(0,2+tr*10+rng.normal(0,2))
                seq[day,fi["scroll_event_count"]]  = max(0,15+tr*40+rng.normal(0,5))
                seq[day,fi["tab_switches"]]        = max(0,bt+tr*14+rng.normal(0,2))
                seq[day,fi["hour_of_day"]]         = np.clip(14+tr*8+rng.normal(0,2),0,23)
                seq[day,fi["day_of_week"]]         = float(day%7)
            seqs.append(seq); labels.append(float(label))
    # Augment
    aug_s, aug_l = list(seqs), list(labels)
    for seq,label in zip(seqs,labels):
        for _ in range(2):
            aug = seq.copy()
            for idx in rng.integers(0,SEQ_LEN,size=rng.integers(1,3)):
                aug[idx] = seq[rng.integers(0,SEQ_LEN)] + rng.normal(0,3,N_FEATURES)
            aug_s.append(aug); aug_l.append(label)
    return np.array(aug_s), np.array(aug_l)


def get_context(seq, model, scaler):
    scaled = scaler.transform(seq)
    h = np.zeros(N_HIDDEN); c = np.zeros(N_HIDDEN)
    hs = []
    for t in range(scaled.shape[0]):
        h,c = model.cell.forward(scaled[t],h,c); hs.append(h.copy())
    H = np.array(hs)
    a = np.exp(H@model.W_attn - (H@model.W_attn).max())
    a /= a.sum()
    return (H*a[:,None]).sum(axis=0)


def train():
    print("="*60)
    print("KOGNI LSTM TRAINER (Pure NumPy — no PyTorch)")
    print("="*60)
    np.random.seed(42)

    print("\n[DATA] Generating sequences...")
    X_raw, y = generate_sequences(200, 42)
    print(f"       {len(X_raw)} sequences")

    flat = X_raw.reshape(-1, N_FEATURES)
    scaler = StandardScaler().fit(flat)

    idx = np.random.permutation(len(X_raw))
    sp  = int(len(X_raw)*0.8)
    Xtr, ytr = X_raw[idx[:sp]], y[idx[:sp]]
    Xvl, yvl = X_raw[idx[sp:]], y[idx[sp:]]

    model = KogniLSTMNumpy(N_FEATURES, N_HIDDEN)
    lr, epochs, best_acc = 0.05, 80, 0

    print(f"\n[TRAIN] Epochs: {epochs}")
    for ep in range(1, epochs+1):
        Ctr = np.array([get_context(s, model, scaler) for s in Xtr])
        logits = Ctr @ model.W_out + model.b_out
        preds  = sigmoid(logits)
        eps    = 1e-7
        loss   = -np.mean(ytr*np.log(preds+eps)+(1-ytr)*np.log(1-preds+eps))
        dL     = (preds - ytr) / len(ytr)
        model.W_out -= lr * (Ctr.T @ dL)
        model.b_out -= lr * dL.sum()
        # Simple attention gradient — scalar per sample
        for i, seq in enumerate(Xtr):
            scaled = scaler.transform(seq)
            h=np.zeros(N_HIDDEN); c=np.zeros(N_HIDDEN); hs=[]
            for t in range(scaled.shape[0]):
                h,c=model.cell.forward(scaled[t],h,c); hs.append(h.copy())
            H = np.array(hs)
            a = np.exp(H@model.W_attn-(H@model.W_attn).max()); a/=a.sum()
            ctx = (H*a[:,None]).sum(axis=0)
            d_ctx = dL[i] * model.W_out
            d_a   = H @ d_ctx
            d_attn_raw = a*(d_a - (a*d_a).sum())
            model.W_attn -= lr * (H.T @ d_attn_raw) * 0.1

        if ep%10==0 or ep==1:
            Cvl = np.array([get_context(s,model,scaler) for s in Xvl])
            vp  = sigmoid(Cvl@model.W_out+model.b_out)
            acc = accuracy_score(yvl,(vp>0.5).astype(int))
            print(f"        Epoch {ep:3d} | loss: {loss:.4f} | val_acc: {acc:.4f}")
            if acc > best_acc:
                best_acc = acc
                model.save(str(MODEL_DIR/"lstm_best.json"))

    Cvl = np.array([get_context(s,model,scaler) for s in Xvl])
    vp  = sigmoid(Cvl@model.W_out+model.b_out)
    print(f"\n[EVAL] Best val accuracy: {best_acc:.4f}")
    print(f"       Final val accuracy: {accuracy_score(yvl,(vp>0.5).astype(int)):.4f}")

    joblib.dump(scaler, MODEL_DIR/"lstm_scaler.joblib")
    json.dump({
        "input_size": N_FEATURES, "hidden_size": N_HIDDEN,
        "seq_len": SEQ_LEN, "feature_cols": FEATURE_COLS,
        "best_val_acc": round(best_acc,4), "backend": "numpy"
    }, open(MODEL_DIR/"lstm_metadata.json","w"), indent=2)

    print(f"\n[SAVE] lstm_best.json, lstm_scaler.joblib, lstm_metadata.json → {MODEL_DIR}/")
    print(f"\n✓ LSTM training complete.")


if __name__ == "__main__":
    train()
