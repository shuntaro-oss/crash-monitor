"""ニュース・地政学の補助スコア（GDELT DOC 2.0。無料・キー不要）。モデル本体には含めず、別枠で表示する。
SNSの要人発言は有料APIが必要なため、data/manual/watchlist.json に手入力できる形にしてある。"""
from __future__ import annotations

import json
import time
import urllib.parse

import numpy as np
import pandas as pd

import config
from data import _http_get

GDELT = "https://api.gdeltproject.org/api/v2/doc/doc"


def _tone_z(query: str) -> float | None:
    q = urllib.parse.quote(f"{query} sourcelang:english")
    raw = _http_get(f"{GDELT}?query={q}&mode=timelinetone&timespan=12months&format=json")
    tl = json.loads(raw)["timeline"][0]["data"]
    s = pd.Series({pd.to_datetime(d["date"]).tz_localize(None): d["value"] for d in tl}).sort_index()
    if len(s) < 60:
        return None
    recent, base = s.iloc[-30:].mean(), s.mean()
    sd = s.std()
    return float(-(recent - base) / sd) if sd > 0 else 0.0   # トーンが悪化するほどプラス


def _headlines(query: str, n: int = 5) -> list[dict]:
    q = urllib.parse.quote(f"{query} sourcelang:english")
    raw = _http_get(f"{GDELT}?query={q}&mode=artlist&maxrecords={n}&sort=hybridrel&timespan=7d&format=json")
    return [{"title": a.get("title", ""), "url": a.get("url", ""), "domain": a.get("domain", "")}
            for a in json.loads(raw).get("articles", [])]


def load_watchlist() -> list[dict]:
    p = config.MANUAL_DIR / "watchlist.json"
    if not p.exists():
        return []
    return json.loads(p.read_text(encoding="utf-8"))


def news_stress(enabled: bool = True) -> dict:
    out = {"themes": [], "score": None, "watchlist": load_watchlist(), "note": ""}
    zs = []
    if enabled:
        for theme, query in config.NEWS_QUERIES.items():
            try:
                z = _tone_z(query)
                time.sleep(5.5)  # GDELTのレート制限対策
                heads = _headlines(query)
                time.sleep(5.5)
            except Exception as e:  # noqa: BLE001
                out["themes"].append({"theme": theme, "z": None, "headlines": [], "error": str(e)})
                continue
            out["themes"].append({"theme": theme, "z": z, "headlines": heads})
            if z is not None:
                zs.append(z)
    if zs:
        out["score"] = float(np.clip(50 + 15 * np.mean(zs), 0, 100))
    sev = [w.get("severity", 0) for w in out["watchlist"]]
    if sev:  # 手入力の重大度(0-3)の最大値を加点
        out["score"] = float(np.clip((out["score"] if out["score"] is not None else 50) + 5 * max(sev), 0, 100))
    if out["score"] is None:
        out["note"] = "ニュースを取得できなかったため、補助スコアは算出していません。"
    return out
