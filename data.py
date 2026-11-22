"""データ取得。標準ライブラリ+pandasのみ。取得失敗時は data/manual/ のCSVにフォールバック。"""
from __future__ import annotations

import io
import json
import time
import urllib.request

import pandas as pd

import config

UA = {"User-Agent": "Mozilla/5.0 (crash-monitor)"}


def _http_get(url: str, timeout: int = 25, retries: int = 1) -> bytes:
    last = None
    for _ in range(retries + 1):
        t0 = time.time()
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                raw = r.read()
            print(f"  取得OK {time.time()-t0:.1f}s {url[:70]}", flush=True)
            return raw
        except Exception as e:  # noqa: BLE001
            last = e
            print(f"  取得NG {time.time()-t0:.1f}s {url[:70]} {e}", flush=True)
    raise last


def _cached(name: str, loader, max_age_h: float = 20.0) -> pd.Series:
    config.CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = config.CACHE_DIR / f"{name}.csv"
    if path.exists() and (time.time() - path.stat().st_mtime) < max_age_h * 3600:
        s = pd.read_csv(path, index_col=0, parse_dates=True).iloc[:, 0]
        return s
    s = loader()
    s.to_csv(path, header=["value"])
    return s


_FRED_DOWN = {"n": 0}   # fredgraph.csv が連続で失敗したら以後は試さない（待ち時間の節約）


def _fred_csv(series_id: str) -> pd.Series:
    raw = _http_get(f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}", timeout=40, retries=0)
    df = pd.read_csv(io.BytesIO(raw))
    s = pd.to_numeric(df.iloc[:, 1], errors="coerce")
    s.index = pd.to_datetime(df.iloc[:, 0])
    s.name = series_id
    return s.dropna()


def _fred_api(series_id: str) -> pd.Series:
    import os
    key = os.environ.get("FRED_API_KEY")
    if not key:
        raise RuntimeError("FRED_API_KEYなし")
    raw = _http_get("https://api.stlouisfed.org/fred/series/observations"
                    f"?series_id={series_id}&api_key={key}&file_type=json", timeout=40, retries=0)
    obs = json.loads(raw)["observations"]
    s = pd.Series({pd.Timestamp(o["date"]): o["value"] for o in obs})
    return pd.to_numeric(s, errors="coerce").dropna()


def _yahoo_macro(series_id: str) -> pd.Series:
    sym = config.YAHOO_FALLBACK[series_id]
    s = _fetch_yahoo(sym)
    if series_id in ("GS10", "TB3MS"):   # 利回りが10倍表記の期間があるため補正
        s = s.where(s <= 30, s / 10)
    return s


def fetch_fred(series_id: str) -> pd.Series:
    def load():
        errors = []
        steps = []
        if _FRED_DOWN["n"] < 2:
            steps.append(("fredgraph", _fred_csv))
        steps.append(("fredapi", _fred_api))
        if series_id in config.YAHOO_FALLBACK:
            steps.append(("yahoo代替", _yahoo_macro))
        for name, fn in steps:
            try:
                s = fn(series_id)
                if name == "fredgraph":
                    _FRED_DOWN["n"] = 0
                if len(s) > 12:
                    return s
            except Exception as e:  # noqa: BLE001
                errors.append(f"{name}: {e}")
                if name == "fredgraph":
                    _FRED_DOWN["n"] += 1
        raise RuntimeError("; ".join(errors))
    return _cached(f"fred_{series_id}", load)


def _fetch_yahoo(symbol: str) -> pd.Series:
    sym = urllib.request.quote(symbol)
    now = int(time.time())
    raw = _http_get(f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}"
                    f"?period1=-631152000&period2={now}&interval=1d")
    res = json.loads(raw)["chart"]["result"][0]
    idx = pd.to_datetime(res["timestamp"], unit="s").normalize()
    close = res["indicators"]["quote"][0]["close"]
    s = pd.Series(close, index=idx, dtype="float64").dropna()
    s = s[~s.index.duplicated(keep="last")]
    print(f"  Yahoo {symbol}: {len(s)}行 {s.index[0]:%Y-%m-%d}〜{s.index[-1]:%Y-%m-%d}", flush=True)
    return s


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
            errors.append(f"{name}: 行数不足({len(s)}行)")
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
