"""暴落事象の自動検出と、手動整理した原因カタログ。"""
from __future__ import annotations

import pandas as pd

import config


def find_bear_episodes(px: pd.Series, thr: float = config.BEAR_THRESHOLD) -> pd.DataFrame:
    """高値から thr 以下に下落した局面（長期下落型）。trigger_date=しきい値を割った日。"""
    rows = []
    peak_val, peak_date = -1.0, None
    in_ep, ep = False, {}
    for d, v in px.items():
        if v >= peak_val:
            if in_ep:  # 前回高値を回復 → 終了
                rows.append(ep)
                in_ep = False
            peak_val, peak_date = v, d
            continue
        dd = v / peak_val - 1
        if not in_ep and dd <= thr:
            in_ep = True
            ep = {"kind": "bear", "peak_date": peak_date, "trigger_date": d,
                  "trough_date": d, "depth": dd}
        if in_ep and dd < ep["depth"]:
            ep["depth"], ep["trough_date"] = dd, d
    if in_ep:
        rows.append(ep)
    return pd.DataFrame(rows, columns=["kind", "peak_date", "trigger_date", "trough_date", "depth"])


def find_shock_episodes(px: pd.Series, thr: float = config.SHOCK_THRESHOLD,
                        win: int = config.SHOCK_WINDOW,
                        merge_days: int = config.SHOCK_MERGE_DAYS) -> pd.DataFrame:
    """21営業日で thr 以下の急落（急落型）。近接する発生は1事象にまとめる。"""
    r = px / px.shift(win) - 1
    hits = r[r <= thr]
    rows, last = [], None
    for d, v in hits.items():
        if last is None or (d - last).days > merge_days:
            i = px.index.get_loc(d)
            rows.append({"kind": "shock", "peak_date": px.index[max(i - win, 0)],
                         "trigger_date": d, "trough_date": d, "depth": v})
        else:
            if v < rows[-1]["depth"]:
                rows[-1]["depth"], rows[-1]["trough_date"] = v, d
        last = d
    return pd.DataFrame(rows, columns=["kind", "peak_date", "trigger_date", "trough_date", "depth"])


# ---- 原因カタログ（手動整理。公知の主要事象のみ。内容は要確認） ----
# (開始年月, 終了年月, 市場, 名称, 原因カテゴリ, 概要)
KNOWN_EVENTS = [
    ("1973-01", "1974-12", "US", "オイルショック相場", "インフレ・金利/供給ショック",
     "第一次石油危機とブレトンウッズ体制崩壊後のインフレ、景気後退が重なった。"),
    ("1987-10", "1987-10", "US", "ブラックマンデー", "需給・金利",
     "金利上昇とドル不安の中、ポートフォリオ・インシュアランス等のプログラム売買が下げを増幅した。"),
    ("1990-01", "1992-12", "JP", "バブル崩壊", "バブル・金融引き締め",
     "資産価格の過熱の後、日銀の急速な利上げと不動産向け融資の総量規制が重なった。"),
    ("1997-07", "1998-10", "US", "アジア通貨危機・LTCM", "通貨・金融危機",
     "タイから広がった通貨危機とロシア危機、LTCMの破綻懸念で信用不安が強まった。"),
    ("2000-03", "2002-10", "US", "ITバブル崩壊", "バブル（バリュエーション）",
     "ITセクターの極端な割高が是正され、利上げと景気減速が下げを長引かせた。"),
    ("2007-10", "2009-03", "US", "リーマン・ショック", "信用収縮・金融危機",
     "サブプライム問題が金融機関の連鎖的な信用不安に拡大した。"),
    ("2011-07", "2011-10", "US", "欧州債務危機・米国債格下げ", "ソブリン危機・政治",
     "欧州の財政不安と米国債格下げ、債務上限問題が重なった。"),
    ("2015-08", "2016-02", "US", "チャイナショック", "新興国・通貨",
     "人民元切り下げと中国景気の減速懸念が世界株安を招いた。"),
    ("2018-10", "2018-12", "US", "FRB利上げ・貿易摩擦", "金融引き締め・通商",
     "FRBの利上げ継続と米中貿易摩擦への警戒で急落した。"),
    ("2020-02", "2020-04", "US", "コロナショック", "外生ショック（感染症）",
     "世界的な感染拡大による経済停止への懸念で、史上最速級の下落となった。"),
    ("2022-01", "2022-10", "US", "インフレ・急速な利上げ", "インフレ・金融引き締め",
     "インフレ高進に対するFRBの急速な利上げで、株と債券が同時に下落した。"),
    ("2024-08", "2024-08", "JP", "円キャリー巻き戻し", "金融政策・為替",
     "日銀の利上げと米景気指標の悪化で急激な円高が進み、日経平均が1日で大幅下落した。"),
    ("2025-04", "2025-04", "US", "関税ショック", "通商政策・政治",
     "米国の大幅な関税発表で景気後退懸念が強まり、世界的に急落した。"),
]


def attach_causes(events: pd.DataFrame, market: str) -> pd.DataFrame:
    """検出した事象に、期間が重なる原因カタログ項目を付ける（日本の事象は米国の世界的ショックも許容）。"""
    out = events.copy()
    names, cats, notes = [], [], []
    for _, e in out.iterrows():
        a = e["peak_date"] - pd.Timedelta(days=31)
        b = e["trough_date"] + pd.Timedelta(days=31)
        hit = None
        for s, t, mk, nm, cat, note in KNOWN_EVENTS:
            s_d = pd.Timestamp(s) ; t_d = pd.Timestamp(t) + pd.offsets.MonthEnd(0)
            if mk != market and not (market == "JP" and mk == "US"):
                continue
            if s_d <= b and t_d >= a:
                if hit is None or mk == market:
                    hit = (nm, cat, note)
        names.append(hit[0] if hit else "")
        cats.append(hit[1] if hit else "")
        notes.append(hit[2] if hit else "")
    out["name"], out["category"], out["note"] = names, cats, notes
    return out
