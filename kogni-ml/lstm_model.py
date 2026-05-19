"""
Kogni LSTM — Pure NumPy Implementation
=======================================
No PyTorch, no DLL issues. Works everywhere.
"""

import numpy as np


def sigmoid(x):
    return 1 / (1 + np.exp(-np.clip(x, -500, 500)))


def tanh(x):
    return np.tanh(np.clip(x, -500, 500))


class LSTMCell:
    def __init__(self, input_size: int, hidden_size: int):
        scale    = np.sqrt(2.0 / (input_size + hidden_size))
        combined = input_size + hidden_size
        self.Wf = np.random.randn(hidden_size, combined) * scale
        self.Wi = np.random.randn(hidden_size, combined) * scale
        self.Wo = np.random.randn(hidden_size, combined) * scale
        self.Wc = np.random.randn(hidden_size, combined) * scale
        self.bf = np.zeros(hidden_size)
        self.bi = np.ones(hidden_size)
        self.bo = np.zeros(hidden_size)
        self.bc = np.zeros(hidden_size)

    def forward(self, x, h, c):
        combined = np.concatenate([h, x])
        f = sigmoid(self.Wf @ combined + self.bf)
        i = sigmoid(self.Wi @ combined + self.bi)
        o = sigmoid(self.Wo @ combined + self.bo)
        g = tanh(self.Wc @ combined + self.bc)
        c_new = f * c + i * g
        h_new = o * tanh(c_new)
        return h_new, c_new


class KogniLSTMNumpy:
    def __init__(self, input_size: int = 11, hidden_size: int = 32):
        self.input_size  = input_size
        self.hidden_size = hidden_size
        self.cell        = LSTMCell(input_size, hidden_size)
        self.W_attn      = np.random.randn(hidden_size) * 0.1
        scale            = np.sqrt(2.0 / hidden_size)
        self.W_out       = np.random.randn(hidden_size) * scale
        self.b_out       = np.zeros(1)

    def forward(self, seq: np.ndarray) -> float:
        h = np.zeros(self.hidden_size)
        c = np.zeros(self.hidden_size)
        hidden_states = []
        for t in range(seq.shape[0]):
            h, c = self.cell.forward(seq[t], h, c)
            hidden_states.append(h.copy())
        hidden_arr   = np.array(hidden_states)
        attn_scores  = hidden_arr @ self.W_attn
        attn_weights = np.exp(attn_scores - attn_scores.max())
        attn_weights /= attn_weights.sum()
        context = (hidden_arr * attn_weights[:, None]).sum(axis=0)
        return float(sigmoid(self.W_out @ context + self.b_out).flat[0])

    def predict_batch(self, sequences: np.ndarray) -> np.ndarray:
        return np.array([self.forward(seq) for seq in sequences])

    def save(self, path: str):
        import json
        data = {
            "input_size":  self.input_size,
            "hidden_size": self.hidden_size,
            "Wf": self.cell.Wf.tolist(), "Wi": self.cell.Wi.tolist(),
            "Wo": self.cell.Wo.tolist(), "Wc": self.cell.Wc.tolist(),
            "bf": self.cell.bf.tolist(), "bi": self.cell.bi.tolist(),
            "bo": self.cell.bo.tolist(), "bc": self.cell.bc.tolist(),
            "W_attn": self.W_attn.tolist(),
            "W_out":  self.W_out.tolist(),
            "b_out":  self.b_out.tolist(),
        }
        with open(path, "w") as f:
            json.dump(data, f)

    @classmethod
    def load(cls, path: str) -> "KogniLSTMNumpy":
        import json
        with open(path) as f:
            d = json.load(f)
        m = cls(d["input_size"], d["hidden_size"])
        m.cell.Wf = np.array(d["Wf"]); m.cell.Wi = np.array(d["Wi"])
        m.cell.Wo = np.array(d["Wo"]); m.cell.Wc = np.array(d["Wc"])
        m.cell.bf = np.array(d["bf"]); m.cell.bi = np.array(d["bi"])
        m.cell.bo = np.array(d["bo"]); m.cell.bc = np.array(d["bc"])
        m.W_attn  = np.array(d["W_attn"])
        m.W_out   = np.array(d["W_out"])
        m.b_out   = np.array(d["b_out"])
        return m
