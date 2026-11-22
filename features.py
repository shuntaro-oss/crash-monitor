"""月次の特徴量を作る。最終行が「現在」。"""
from __future__ import annotations

import numpy as np
import pandas as pd


def _monthly(s: pd.Series) -> pd.Series:
    return s.resample("ME").last()


def build_features(px: pd.Series, fred: dict) -> pd.DataFrame:
    px = px.dropna()
    m = _monthly(px)
    hi12 = px.rolling(252, min_periods=120).max().resample("ME").last()
    f = pd.DataFrame(index=m.index)
    f["dd"] = m / hi12 - 1
    f["ret12"] = m.pct_change(12)
    lr = np.log(px).diff()
    f["vol3"] = (lr.rolling(63, min_periods=40).std() * np.sqrt(252)).resample("ME").last()
    f["val"] = np.log(m / m.rolling(120, min_periods=96).mean())
    f["price"] = m
    # 最終月が未完了なら、索引を実際の最終取引日にする（基準日の表示を正確にする）
    if f.index[-1] > px.index[-1]:
        f.index = f.index[:-1].append(pd.DatetimeIndex([px.index[-1]]))

    def mon(sid):
        return _monthly(fred[sid]).reindex(f.index).ffill() if sid in fred else None

    gs10, tb3, baa, ff = mon("GS10"), mon("TB3MS"), mon("BAA"), mon("FEDFUNDS")
    if gs10 is not None and tb3 is not None:
        f["curve"] = gs10 - tb3
    if gs10 is not None and baa is not None:
        f["credit"] = baa - gs10
    if ff is not None:
        f["ff_chg12"] = ff - ff.shift(12)
    # 公表遅れを考慮して1か月ずらす（将来情報の混入を防ぐ）
    cpi, ur = mon("CPIAUCSL"), mon("UNRATE")
    if cpi is not None:
        f["cpi_yoy"] = cpi.pct_change(12).shift(1) * 100
    if ur is not None:
        f["unrate_chg12"] = (ur - ur.shift(12)).shift(1)
    fx = mon("DEXJPUS")
    if fx is not None:
        f["usdjpy_chg12"] = fx.pct_change(12)
    # ---- ダリオ型（債務サイクル）。四半期データは公表遅れを見て6か月ずらす ----
    def qtr(sid):
        return _monthly(fred[sid]).reindex(f.index).ffill().shift(6) if sid in fred else None

    gov = qtr("GFDEGDQ188S")
    if gov is not None:
        f["gov_debt"] = gov
        f["gov_debt_chg5"] = gov - gov.shift(60)
    cm, bc, gdp = qtr("CMDEBT"), qtr("BCNSDODNS"), qtr("GDP")
    if cm is not None and bc is not None and gdp is not None:
        priv = (cm + bc) / 1000 / gdp * 100       # 民間債務/GDP(%)。債務は百万ドル、GDPは十億ドル
        f["priv_debt_chg5"] = priv - priv.shift(60)
    eq = qtr("NCBEILQ027S")
    if eq is not None and gdp is not None:
        f["equity_gdp"] = eq / 1000 / gdp * 100   # 株式時価総額/GDP(%)
    if ff is not None and "cpi_yoy" in f:
        f["real_ff"] = ff - f["cpi_yoy"]
    return f
