"""データ取得。標準ライブラリ+pandasのみ。取得失敗時は data/manual/ のCSVにフォールバック。"""
from __future__ import annotations

import io
import json
import time
import urllib.request

import pandas as pd

import config

UA = {"User-Agent": "Mozilla/5.0 (crash-monitor)"}


def _http_get(url: str, timeout: int = 60) -> bytes:
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def _cached(name: str, loader, max_age_h: float = 20.0) -> pd.Series:
    config.CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = config.CACHE_DIR / f"{name}.csv"
    if path.exists() and (time.time() - path.stat().st_mtime) < max_age_h * 3600:
        s = pd.read_csv(path, index_col=0, parse_dates=True).iloc[:, 0]
        return s
    s = loader()
    s.to_csv(path, header=["value"])
    return s


def fetch_fred(series_id: str) -> pd.Series:
    def load():
        raw = _http_get(f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}")
        df = pd.read_csv(io.BytesIO(raw))
        df.iloc[:, 0] = pd.to_datetime(df.iloc[:, 0])
        s = pd.to_numeric(df.iloc[:, 1], errors="coerce")
        s.index = df.iloc[:, 0]
        s.name = series_id
        return s.dropna()
    return _cached(f"fred_{series_id}", load)


def _fetch_yahoo(symbol: str) -> pd.Series:
    sym = urllib.request.quote(symbol)
    raw = _http_get(f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}?range=max&interval=1d")
    res = json.loads(raw)["chart"]["result"][0]
    idx = pd.to_datetime(res["timestamp"], unit="s").normalize()
    close = res["indicators"]["quote"][0]["close"]
    s = pd.Series(close, index=idx, dtype="float64").dropna()
    return s[~s.index.duplicated(keep="last")]


def _fetch_stooq(symbol: str) -> pd.Series:
    raw = _http_get(f"https://stooq.com/q/d/l/?s={urllib.request.quote(symbol)}&i=d")
    df = pd.read_csv(io.BytesIO(raw), parse_dates=["Date"])
    return df.set_index("Date")["Close"].dropna()


def _manual_prices(key: str) -> pd.Series | None:
    p = config.MANUAL_DIR / f"{key}.csv"
    if not p.exists():
        return None
    df = pd.read_csv(p, parse_dates=["Date"])
    return df.set_index("Date")["Close"].dropna().sort_index()


def fetch_prices(key: str) -> pd.Series:
    """日次終値。Yahoo → Stooq → 手動CSV の順に試す。"""
    m = config.MARKETS[key]
    errors = []
    for name, fn, arg in (("yahoo", _fetch_yahoo, m["yahoo"]), ("stooq", _fetch_stooq, m["stooq"])):
        try:
            s = _cached(f"px_{key}_{name}", lambda fn=fn, arg=arg: fn(arg))
            if len(s) > 1000:
                return s.sort_index()
        except Exception as e:  # noqa: BLE001
            errors.append(f"{name}: {e}")
    s = _manual_prices(key)
    if s is not None and len(s) > 1000:
        return s
    raise RuntimeError(
        f"{key}の株価を取得できませんでした（{'; '.join(errors)}）。"
        f"data/manual/{key}.csv に Date,Close 形式で置けば読み込みます。"
    )


def load_all(markets: list[str]) -> dict:
    """{'px': {市場: Series}, 'fred': {ID: Series}} を返す。"""
    fred = {}
    for sid in config.FRED_SERIES:
        try:
            fred[sid] = fetch_fred(sid)
        except Exception as e:  # noqa: BLE001
            print(f"[警告] FRED {sid} を取得できません: {e}")
    px = {k: fetch_prices(k) for k in markets}
    return {"px": px, "fred": fred}
