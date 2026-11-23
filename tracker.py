"""毎日の予測を記録し、12か月後に実際の結果と照らし合わせる（答え合わせ）。"""
from __future__ import annotations

from datetime import date

import pandas as pd

import config

PATH = config.OUT_DIR / "history.csv"
COLS = ["date", "market", "kind", "horizon", "p", "base", "bubble"]


def log_predictions(results: dict) -> pd.DataFrame:
    """今日の予測を history.csv に追記（同じ日の再実行は上書き）。"""
    config.OUT_DIR.mkdir(exist_ok=True)
    old = pd.read_csv(PATH) if PATH.exists() else pd.DataFrame(columns=COLS)
    if "horizon" not in old.columns:      # 旧形式（12か月のみ）
        old["horizon"] = 12
    old = old.reindex(columns=COLS)
    today = str(date.today())
    rows = []
    for key, r in results.items():
        bub = r["bubble"]["score"] if "bubble" in r else None
        for h, models in r.get("horizons", {12: r["models"]}).items():
            for kind, m in models.items():
                rows.append({"date": today, "market": key, "kind": kind, "horizon": h, "p": round(m["p_now"], 4),
                             "base": round(m["base_rate"], 4), "bubble": None if bub is None else round(bub, 1)})
    new = pd.DataFrame(rows, columns=COLS)
    out = pd.concat([old[old["date"] != today], new], ignore_index=True).sort_values(["date", "market", "kind", "horizon"])
    out.to_csv(PATH, index=False)
    return out


def score(hist: pd.DataFrame, results: dict) -> dict:
    """12か月以上前の記録に、実際の結果（暴落が起きたか）を付けて集計する。"""
    out = {"first": None, "n_total": len(hist), "n_scored": 0, "rows": []}
    if hist.empty:
        return out
    hist = hist.copy()
    if "horizon" not in hist.columns:
        hist["horizon"] = 12
    hist["date"] = pd.to_datetime(hist["date"])
    out["first"] = hist["date"].min()
    today = pd.Timestamp(date.today())
    for (mk, kind, h), g in hist.groupby(["market", "kind", "horizon"]):
        g = g[g["date"] <= today - pd.DateOffset(months=int(h))]   # 期間が過ぎた記録だけ採点
        if g.empty:
            continue
        ev = results[mk]["events"]
        trig = pd.DatetimeIndex(ev[ev["kind"] == kind]["trigger_date"])
        hit = [bool(((trig > d) & (trig <= d + pd.DateOffset(months=int(h)))).any()) for d in g["date"]]
        out["rows"].append({"market": mk, "kind": kind, "horizon": int(h), "n": len(g),
                            "predicted": float(g["p"].mean()), "actual": float(sum(hit) / len(hit))})
        out["n_scored"] += len(g)
    return out
