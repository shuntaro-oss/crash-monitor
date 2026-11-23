"""暴落確率モデル（ロジスティック回帰）。「今後12か月以内に発生する確率」を推定する。"""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss, roc_auc_score
from sklearn.preprocessing import StandardScaler

import config


def make_labels(index: pd.DatetimeIndex, events: pd.DataFrame, dd: pd.Series, kind: str,
                horizon: int = config.HORIZON_MONTHS) -> pd.Series:
    """各月末から12か月以内に事象（しきい値到達）があれば1。直近12か月分は未確定でNaN。"""
    trig = pd.DatetimeIndex(events["trigger_date"]) if len(events) else pd.DatetimeIndex([])
    y = pd.Series(0.0, index=index)
    for t in index:
        end = t + pd.DateOffset(months=horizon)
        y[t] = float(((trig > t) & (trig <= end)).any())
    y[index > index[-1] - pd.DateOffset(months=horizon)] = np.nan
    if kind == "bear":  # すでに-20%以下の局面は「新規発生」ではないので除外
        y[dd <= config.BEAR_THRESHOLD] = np.nan
    return y


def _fit(X: np.ndarray, y: np.ndarray):
    sc = StandardScaler().fit(X)
    clf = LogisticRegression(C=config.LOGIT_C, max_iter=1000).fit(sc.transform(X), y)
    return sc, clf


def _prob(sc, clf, X):
    return clf.predict_proba(sc.transform(X))[:, 1]


def walk_forward(X: pd.DataFrame, y: pd.Series, horizon: int = config.HORIZON_MONTHS) -> dict:
    """拡張窓の前進検証。学習とテストの間に12か月の空白を置き、ラベルの重なりによる漏れを防ぐ。"""
    idx = X.index
    start = idx[0] + pd.DateOffset(years=config.MIN_TRAIN_YEARS)
    preds = pd.Series(np.nan, index=idx)
    t0 = start
    while t0 < idx[-1]:
        t1 = t0 + pd.DateOffset(years=config.TEST_BLOCK_YEARS)
        tr = (idx < t0 - pd.DateOffset(months=max(horizon, 1))) & y.notna().values
        te = (idx >= t0) & (idx < t1) & y.notna().values
        if tr.sum() > 60 and te.sum() > 0 and y[tr].nunique() == 2:
            sc, clf = _fit(X[tr].values, y[tr].values)
            preds[te] = _prob(sc, clf, X[te].values)
        t0 = t1
    ok = preds.notna() & y.notna()
    res = {"n_test": int(ok.sum()), "auc": None, "brier": None, "brier_base": None,
           "preds": preds[ok], "y": y[ok]}
    if ok.sum() > 0 and y[ok].nunique() == 2:
        res["auc"] = float(roc_auc_score(y[ok], preds[ok]))
        res["brier"] = float(brier_score_loss(y[ok], preds[ok]))
        res["brier_base"] = float(brier_score_loss(y[ok], np.full(ok.sum(), y[ok].mean())))
    return res


def analyze(feat: pd.DataFrame, events: pd.DataFrame, cols: list[str], kind: str,
            horizon: int = config.HORIZON_MONTHS) -> dict:
    cols = [c for c in cols if c in feat.columns]
    data = feat[cols].copy()
    valid = data.notna().all(axis=1)
    X = data[valid]
    y_all = make_labels(feat.index, events, feat["dd"], kind, horizon)
    y = y_all[valid]
    labeled = y.notna()
    Xl, yl = X[labeled], y[labeled]
    if len(Xl) < 120 or yl.sum() < 8:
        raise RuntimeError(f"学習データが不足しています（行数{len(Xl)}, 事象{int(yl.sum())}）")

    sc, clf = _fit(Xl.values, yl.values)
    now_x = X.iloc[[-1]]
    p_now = float(_prob(sc, clf, now_x.values)[0])

    # ブロックブートストラップ（12か月単位）で幅を出す
    rng = np.random.default_rng(0)
    blocks = np.array_split(np.arange(len(Xl)), max(len(Xl) // 12, 1))
    boots = []
    for _ in range(config.BOOTSTRAP_N):
        pick = np.concatenate([blocks[i] for i in rng.integers(0, len(blocks), len(blocks))])
        yy = yl.values[pick]
        if yy.sum() < 3 or yy.sum() == len(yy):
            continue
        s2, c2 = _fit(Xl.values[pick], yy)
        boots.append(float(_prob(s2, c2, now_x.values)[0]))
    lo, hi = (np.percentile(boots, [10, 90]) if boots else (np.nan, np.nan))

    # 要因分解（ロジット寄与 = 係数 × 標準化値）
    z = sc.transform(now_x.values)[0]
    contrib = pd.Series(clf.coef_[0] * z, index=cols).sort_values(ascending=False)

    # 類似局面（標準化空間の距離）
    Z = sc.transform(X.values)
    dist = pd.Series(np.linalg.norm(Z - z, axis=1), index=X.index)
    dist = dist[dist.index < X.index[-1] - pd.DateOffset(months=24)].sort_values()
    analogs, chosen = [], []
    trig = pd.DatetimeIndex(events["trigger_date"]) if len(events) else pd.DatetimeIndex([])
    for d, v in dist.items():
        if all(abs((d - c).days) > 365 for c in chosen):
            chosen.append(d)
            nxt = trig[(trig > d) & (trig <= d + pd.DateOffset(months=horizon))]
            analogs.append({"date": d, "dist": float(v),
                            "outcome": f"{horizon}か月以内に発生" if len(nxt) else "発生せず"})
        if len(analogs) >= 5:
            break

    fitted = pd.Series(_prob(sc, clf, X.values), index=X.index)  # 全期間（学習データ内）の推定値
    return {
        "kind": kind, "p_now": p_now, "p_lo": float(lo), "p_hi": float(hi),
        "base_rate": float(yl.mean()), "n_rows": int(len(Xl)), "n_pos": int(yl.sum()),
        "contrib": contrib, "now_values": now_x.iloc[0], "analogs": analogs,
        "cv": walk_forward(X, y_all[valid], horizon), "horizon": horizon, "fitted": fitted, "asof": X.index[-1],
    }
