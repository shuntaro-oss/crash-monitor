"""HTMLレポート出力（外部ライブラリ不要。グラフはインラインSVG）。"""
from __future__ import annotations

import html
from datetime import datetime

import pandas as pd

import config

CSS = """
body{font-family:'Yu Gothic','Hiragino Sans',sans-serif;max-width:960px;margin:24px auto;padding:0 14px;color:#222;line-height:1.6}
h1{font-size:22px}h2{font-size:18px;border-bottom:2px solid #ddd;padding-bottom:4px;margin-top:32px}
table{border-collapse:collapse;width:100%;font-size:14px;margin:8px 0}
th,td{border:1px solid #ddd;padding:6px 8px;text-align:left}th{background:#f4f4f4}
.p{font-size:28px;font-weight:bold}.low{color:#2a7}.mid{color:#d80}.high{color:#c22}
.card{border:1px solid #ddd;border-radius:8px;padding:12px 16px;margin:10px 0}
.note{color:#666;font-size:13px}.warn{background:#fff6e0;border:1px solid #eac;padding:10px;border-radius:6px;font-size:13px}
"""


def _pct(x, d=1):
    return "-" if x is None or pd.isna(x) else f"{x*100:.{d}f}%"


def _level(ratio: float, news: float | None) -> tuple[str, str]:
    if ratio >= 2 or (news or 0) >= 70:
        return "高", "high"
    if ratio >= 1.3 or (news or 0) >= 60:
        return "中", "mid"
    return "低", "low"


def _svg_line(s: pd.Series, events: pd.DataFrame, w=900, h=180) -> str:
    s = s.dropna()
    if len(s) < 2:
        return ""
    x0, x1 = s.index[0].value, s.index[-1].value
    ymax = max(float(s.max()), 0.05)
    X = lambda d: 40 + (d.value - x0) / (x1 - x0) * (w - 50)
    Y = lambda v: h - 20 - v / ymax * (h - 35)
    pts = " ".join(f"{X(d):.1f},{Y(v):.1f}" for d, v in s.items())
    bands = "".join(
        f'<rect x="{X(r.trigger_date):.1f}" y="10" width="3" height="{h-30}" fill="#c22" opacity="0.35"/>'
        for r in events.itertuples() if s.index[0] <= r.trigger_date <= s.index[-1])
    ticks = "".join(f'<text x="2" y="{Y(v)+4:.0f}" font-size="10">{v*100:.0f}%</text>'
                    for v in (0, ymax / 2, ymax))
    return (f'<svg viewBox="0 0 {w} {h}" width="100%">{bands}<polyline points="{pts}" fill="none" '
            f'stroke="#26a" stroke-width="1.5"/>{ticks}</svg>')


def _bubble_section(b: dict) -> str:
    rows = "".join(f"<tr><td>{html.escape(x['name'])}</td><td>{x['value']:.3f}</td><td>{x['pct']:.0f}</td></tr>" for x in b["rows"])
    peaks = "".join(f"<tr><td>{html.escape(p['name'])}</td><td>{p['date']:%Y-%m}</td><td>{p['score']:.0f}</td></tr>" for p in b["peaks"])
    ev = pd.DataFrame({"trigger_date": pd.to_datetime([p["date"] for p in b["peaks"]])})
    return (f'<div class="card"><b>バブル度</b>　<span class="p {b["cls"]}">{b["score"]:.0f}</span> / 100　'
            f'<b class="{b["cls"]}">{b["level"]}</b><br><span class="note">過去の履歴の中での位置（上位何%か）の平均。'
            f'50未満=平常 / 50〜70=やや割高 / 70〜85=割高 / 85以上=バブル警戒。基準月 {b["asof"]:%Y-%m}。'
            f'履歴の最高は {b["max_date"]:%Y-%m} の {b["max_score"]:.0f}。</span></div>'
            f"<h3>バブル度の内訳</h3><table><tr><th>指標</th><th>現在値</th><th>履歴内の位置(0-100)</th></tr>{rows}</table>"
            f"<h3>過去の頂点との比較</h3><table><tr><th>局面</th><th>時期</th><th>バブル度</th></tr>{peaks}</table>"
            f"<h3>バブル度の推移（赤線は上の頂点）</h3>" + _svg_line(b["history"] / 100, ev) +
            '<p class="note">バブルかどうかは崩壊後にしか確定しません。これは予言ではなく、過去の頂点と比べた現在の位置です。</p>')


def _market_section(key: str, r: dict) -> str:
    name = config.MARKETS[key]["name"]
    parts = [f"<h2>{html.escape(name)}</h2>"]
    if "bubble" in r:
        parts.append(_bubble_section(r["bubble"]))
    news = r.get("news_score")
    for kind, label in (("shock", "急落型（21営業日で-10%以上）"), ("bear", "長期下落型（高値から-20%以上）")):
        a = r["models"].get(kind)
        if not a:
            parts.append(f'<div class="card"><b>{label}</b><br>算出できませんでした: {html.escape(r["errors"].get(kind, ""))}</div>')
            continue
        ratio = a["p_now"] / a["base_rate"] if a["base_rate"] else 1
        lv, cls = _level(ratio, news)
        cv = a["cv"]
        cv_txt = (f"前進検証 AUC {cv['auc']:.2f} / Brier {cv['brier']:.3f}（平均予測のみ {cv['brier_base']:.3f}）"
                  if cv["auc"] is not None else "前進検証は事例不足で算出不可")
        parts.append(
            f'<div class="card"><b>{label}　今後12か月以内の発生確率</b><br>'
            f'<span class="p {cls}">{_pct(a["p_now"])}</span>　'
            f'<span class="note">推定幅(10〜90%) {_pct(a["p_lo"])}〜{_pct(a["p_hi"])} ／ '
            f'過去の平均 {_pct(a["base_rate"])} の {ratio:.1f}倍 ／ 警戒レベル <b class="{cls}">{lv}</b></span><br>'
            f'<span class="note">基準月: {a["asof"]:%Y-%m} ／ 学習 {a["n_rows"]}か月・発生前月 {a["n_pos"]}か月 ／ {cv_txt}</span></div>')
        cp = r.get("compare", {}).get(kind)
        if cp:
            f = lambda v: "-" if v is None else f"{v:.3f}"
            parts.append(
                "<h3>ダリオ型（債務サイクル）指標の検証</h3><table><tr><th></th><th>AUC</th><th>Brier（小さいほど良い）</th><th>現在の確率</th></tr>"
                f"<tr><td>通常版</td><td>{f(cp['base']['auc'])}</td><td>{f(cp['base']['brier'])}</td><td>{_pct(cp['p_base'])}</td></tr>"
                f"<tr><td>ダリオ指標を追加</td><td>{f(cp['ext']['auc'])}</td><td>{f(cp['ext']['brier'])}</td><td>{_pct(cp['p_ext'])}</td></tr></table>"
                f"<p class='note'>判定: <b>{'改善したため採用' if cp['adopt'] else '改善が確認できないため不採用（表示中の確率は通常版）'}</b></p>")
        c = a["contrib"]
        rows = "".join(
            f"<tr><td>{config.FEATURE_LABELS.get(k, k)}</td><td>{a['now_values'][k]:.3f}</td>"
            f"<td>{'↑押し上げ' if v > 0 else '↓押し下げ'} {v:+.2f}</td></tr>" for k, v in c.items())
        parts.append(f"<h3>{label}：現在の要因</h3><table><tr><th>指標</th><th>現在値</th><th>確率への寄与(ロジット)</th></tr>{rows}</table>")
        an = "".join(f"<tr><td>{x['date']:%Y-%m}</td><td>{x['dist']:.2f}</td><td>{x['outcome']}</td></tr>" for x in a["analogs"])
        parts.append(f"<h3>{label}：似ている過去の局面</h3><table><tr><th>時期</th><th>距離(小さいほど類似)</th><th>その後</th></tr>{an}</table>")
        if kind == "bear" or "bear" not in r["models"]:
            parts.append("<h3>推定確率の推移（学習データ内の当てはめ。赤線は事象発生）</h3>"
                         + _svg_line(a["fitted"], r["events"][r["events"]["kind"] == kind]))
    ev = r["events"].sort_values("trigger_date", ascending=False)
    rows = "".join(
        f"<tr><td>{'長期' if e.kind=='bear' else '急落'}</td><td>{e.trigger_date:%Y-%m-%d}</td>"
        f"<td>{e.depth*100:.1f}%</td><td>{html.escape(e.name)}</td><td>{html.escape(e.category)}</td>"
        f"<td>{html.escape(e.note)}</td></tr>" for e in ev.itertuples())
    parts.append("<h3>過去の暴落と原因（原因は手動整理。空欄は未整理）</h3>"
                 f"<table><tr><th>型</th><th>発生日</th><th>下落率</th><th>名称</th><th>原因分類</th><th>概要</th></tr>{rows}</table>")
    return "".join(parts)


def _news_section(news: dict) -> str:
    sc = news.get("score")
    p = [f"<h2>ニュース・国政・地政学（補助スコア）</h2>"]
    p.append(f'<div class="card"><span class="p">{"-" if sc is None else f"{sc:.0f}"}</span> / 100　'
             f'<span class="note">50が平常。ニュースのトーンが直近30日で過去12か月より悪化するほど上がる。モデル確率には含めていない。{html.escape(news.get("note",""))}</span></div>')
    for t in news["themes"]:
        z = "取得失敗" if t["z"] is None else f"悪化度 z={t['z']:+.2f}"
        heads = "".join(f'<li><a href="{html.escape(h["url"])}">{html.escape(h["title"])}</a> <span class="note">{html.escape(h["domain"])}</span></li>'
                        for h in t["headlines"])
        p.append(f"<b>{html.escape(t['theme'])}</b>（{z}）<ul>{heads}</ul>")
    if news["watchlist"]:
        rows = "".join(f"<tr><td>{html.escape(str(w.get('item','')))}</td><td>{w.get('severity',0)}</td><td>{html.escape(str(w.get('note','')))}</td></tr>"
                       for w in news["watchlist"])
        p.append(f"<b>手入力ウォッチリスト（要人発言・政策など）</b><table><tr><th>項目</th><th>重大度(0-3)</th><th>メモ</th></tr>{rows}</table>")
    return "".join(p)


def build_html(results: dict, news: dict, demo: bool) -> str:
    body = [f"<h1>暴落モニター　{datetime.now():%Y-%m-%d}</h1>"]
    if demo:
        body.append('<div class="warn"><b>デモデータです。</b>数値は合成データによる動作確認用で、実際の市場とは無関係です。</div>')
    body.append('<div class="warn">確率は「過去の暴落前の指標とどれだけ似ているか」の目安です。事例が少なく、予測が当たることを保証するものではありません。投資判断は自己責任でお願いします。</div>')
    for k, r in results.items():
        body.append(_market_section(k, r))
    body.append(_news_section(news))
    return f"<!doctype html><html lang='ja'><head><meta charset='utf-8'><title>暴落モニター</title><style>{CSS}</style></head><body>{''.join(body)}</body></html>"
