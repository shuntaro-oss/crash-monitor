"""合成データ（動作確認用）。実市場とは無関係。"""
from __future__ import annotations

import numpy as np
import pandas as pd


def make_demo(seed: int = 1) -> dict:
    rng = np.random.default_rng(seed)
    days = pd.bdate_range("1950-01-02", "2026-11-20")
    months = pd.date_range("1949-01-01", "2026-11-01", freq="MS")
    n = len(months)
    curve = np.zeros(n); credit = np.zeros(n) + 1.5; ff = np.zeros(n) + 3
    for i in range(1, n):
        curve[i] = 0.97 * curve[i - 1] + rng.normal(0, 0.25) + 0.02
        credit[i] = 1.5 + 0.96 * (credit[i - 1] - 1.5) + rng.normal(0, 0.12)
        ff[i] = max(0.1, ff[i - 1] + rng.normal(0, 0.15))
    cm = pd.Series(curve, index=months)
    stress = (-(cm) + (pd.Series(credit, index=months) - 1.5)).reindex(days, method="ffill").fillna(0).values
    p = np.zeros(len(days)); vol = 0.008
    for i in range(1, len(days)):
        vol = 0.95 * vol + 0.05 * 0.007 + 0.03 * abs(p[i - 1])
        r = 0.0004 + rng.normal(0, vol)
        if rng.random() < 0.00002 * np.exp(1.2 * stress[i]):   # ストレスが高いほど急落が起きやすい
            r -= rng.uniform(0.04, 0.12)
        p[i] = r
    px = pd.Series(100 * np.exp(np.cumsum(p)), index=days)
    px_jp = px.shift(3).bfill() * (1 + rng.normal(0, 0.003, len(days))).cumprod() ** 0.01
    fred = {
        "TB3MS": pd.Series(ff, index=months).clip(lower=0.1),
        "GS10": pd.Series(ff + curve, index=months).clip(lower=0.3),
        "BAA": pd.Series(ff + curve + credit, index=months).clip(lower=1.0),
        "FEDFUNDS": pd.Series(ff, index=months),
        "CPIAUCSL": pd.Series(100 * np.exp(np.cumsum(rng.normal(0.003, 0.002, n))), index=months),
        "UNRATE": pd.Series(5 + np.cumsum(rng.normal(0, 0.1, n)) * 0.2, index=months).clip(2, 12),
        "DEXJPUS": pd.Series(150 * np.exp(np.cumsum(rng.normal(0, 0.01, n))) * 0.5, index=months),
    }
    qs = pd.date_range("1947-01-01", "2026-07-01", freq="QS")
    g = pd.Series(30 + np.cumsum(rng.normal(0.3, 1.0, len(qs))), index=qs).clip(20, 130)
    fred["GFDEGDQ188S"] = g
    fred["GDP"] = pd.Series(500 * np.exp(np.cumsum(rng.normal(0.015, 0.005, len(qs)))), index=qs)
    fred["CMDEBT"] = fred["GDP"] * 1000 * 0.4 * (1 + 0.1 * np.sin(np.arange(len(qs)) / 12))
    fred["BCNSDODNS"] = fred["GDP"] * 1000 * 0.3 * (1 + 0.1 * np.cos(np.arange(len(qs)) / 15))
    return {"px": {"US": px, "JP": px_jp}, "fred": fred}
