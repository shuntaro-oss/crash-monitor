"""バブル度（0〜100）。各指標が「その市場の過去の履歴の中で上位何%か」を平均した客観的な目安。
バブルかどうかは崩壊後にしか確定しないため、予言ではなく「過去の頂点と比べた今の位置」を示す。"""
from __future__ import annotations

import numpy as np
import pandas as pd

import config

LABELS = {
    "val": "10年平均に対する割高度",
    "ret36": "直近3年の年率上昇率",
    "trend": "長期トレンドからの乖離",
    "equity_gdp": "株式時価総額/GDP（バフェット指標）",
    "priv_debt_chg5": "民間債務/GDPの5年変化（信用の膨張）",
}


def level(score: float) -> tuple[str, str]:
    if score >= 85:
        return "バブル警戒", "high"
    if score >= 70:
        return "割高", "mid"
    if score >= 50:
        return "やや割高", "mid"
    return "平常", "low"


def compute(feat: pd.DataFrame, key: str) -> dict:
    price = feat["price"]
    comp = pd.DataFrame(index=feat.index)
    comp["val"] = feat["val"]
    comp["ret36"] = (price / price.shift(36)) ** (1 / 3) - 1
    t = np.arange(len(price), dtype=float)
    lp = np.log(price)
    ok = lp.notna().values
    k, b = np.polyfit(t[ok], lp.values[ok], 1)
    comp["trend"] = lp - (k * t + b)
    if key == "US":   # 米国のみ（FREDのAPIキーがあるときだけ列が存在）
        for c in ("equity_gdp", "priv_debt_chg5"):
            if c in feat.columns and feat[c].notna().sum() > 240:
                comp[c] = feat[c]
    pct = comp.rank(pct=True) * 100
    score = pct.mean(axis=1)
    score[pct.notna().sum(axis=1) < 3] = np.nan

    now = comp.index[-1]
    rows = [{"name": LABELS[c], "value": float(comp[c].iloc[-1]), "pct": float(pct[c].iloc[-1])}
            for c in comp.columns if pd.notna(comp[c].iloc[-1])]
    peaks = []
    for ym, name in config.BUBBLE_PEAKS.get(key, []):
        d = pd.Timestamp(ym) + pd.offsets.MonthEnd(0)
        i = score.index.get_indexer([d], method="nearest")[0]
        if pd.notna(score.iloc[i]):
            peaks.append({"name": name, "date": score.index[i], "score": float(score.iloc[i])})
    s = float(score.iloc[-1])
    lv, cls = level(s)
    return {"score": s, "level": lv, "cls": cls, "rows": rows, "peaks": peaks,
            "history": score, "asof": now, "max_date": score.idxmax(), "max_score": float(score.max())}
