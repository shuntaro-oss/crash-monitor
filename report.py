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
.sum{display:flex;gap:12px;flex-wrap:wrap;margin:14px 0}
.box{flex:1;min-width:260px;border:2px solid #ddd;border-radius:12px;padding:16px}
.box.green{border-color:#2a7}.box.yellow{border-color:#e9a400}.box.red{border-color:#c22}
.sig{font-size:26px;font-weight:bold;margin:2px 0 10px}.green .sig{color:#2a7}.yellow .sig{color:#c80}.red .sig{color:#c22}
.row{margin:8px 0;font-size:15px}.chip{display:inline-block;padding:2px 10px;border-radius:999px;color:#fff;font-weight:bold;font-size:14px}
.c-low{background:#2a7}.c-mid{background:#e9a400}.c-high{background:#c22}
.gauge{display:flex;height:10px;border-radius:5px;overflow:hidden;margin:4px 0 2px;position:relative}
.gauge i{flex:1}.gauge i:nth-child(1){background:#bfe5d3}.gauge i:nth-child(2){background:#f6e3a8}.gauge i:nth-child(3){background:#f3b9b0}.gauge i:nth-child(4){background:#e08a80}
.mark{position:absolute;top:-3px;width:4px;height:16px;background:#222;border-radius:2px}
details{margin:14px 0}summary{cursor:pointer;font-weight:bold;padding:8px 0}
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


RISK_WORDS = ["平均より低め", "平均並み", "平均より高め", "平均よりかなり高め"]


def _risk(m: dict) -> tuple[int, float]:
    """暴落リスクの段階(0-3)。不確かな推定は割り引く（現在値と下限の幾何平均で平均と比較）。"""
    ratio = ((m["p_now"] * max(m["p_lo"], 1e-4)) ** 0.5) / m["base_rate"] if m["base_rate"] else 1
    lv = 0 if ratio < 0.8 else 1 if ratio < 1.25 else 2 if ratio < 2 else 3
    return lv, ratio


def _gauge(pos: float) -> str:
    """pos: 0〜1。4色の帯の上に印を付ける。"""
    return f'<div class="gauge"><i></i><i></i><i></i><i></i><span class="mark" style="left:calc({pos*100:.0f}% - 2px)"></span></div>'


def _summary_box(key: str, r: dict) -> str:
    name = config.MARKETS[key]["name"]
    b = r.get("bubble")
    levels = [_risk(m) for m in r["models"].values()]
    risk_lv = max((l for l, _ in levels), default=None)
    bscore = b["score"] if b else None
    # 総合の信号
    if (bscore is not None and bscore >= 85) or risk_lv == 3:
        sig, cls = "警戒", "red"
    elif (bscore is not None and bscore >= 70) or (risk_lv is not None and risk_lv >= 2):
        sig, cls = "やや警戒", "yellow"
    else:
        sig, cls = "平常", "green"
    chip = lambda lv: "c-low" if lv <= 0 else "c-mid" if lv <= 2 else "c-high"
    out = [f'<div class="box {cls}"><b>{html.escape(name)}</b><div class="sig">{sig}</div>']
    if b:
        bl = {"平常": 0, "やや割高": 1, "割高": 2, "バブル警戒": 3}[b["level"]]
        out.append(f'<div class="row">バブル度　<span class="chip {chip(bl)}">{b["level"]}</span>{_gauge(min(bscore, 99.9)/100)}</div>')
    if risk_lv is not None:
        out.append(f'<div class="row">暴落リスク　<span class="chip {chip(risk_lv)}">{RISK_WORDS[risk_lv]}</span>{_gauge((risk_lv + 0.5) / 4)}</div>')
        # 主な押し上げ要因（暴落リスクを高めている指標。名前のみ）
        top = None
        for kind in ("bear", "shock"):
            if kind in r["models"]:
                top = r["models"][kind]["contrib"]
                break
        if top is not None:
            ups = [config.FEATURE_LABELS.get(k, k) for k, v in top.items() if v > 0.15][:2]
            if ups:
                out.append(f'<div class="row note">リスクを高めている主な要因：{"、".join(html.escape(u) for u in ups)}</div>')
    out.append("</div>")
    return "".join(out)


def _track_record(r_all: dict, tr: dict | None) -> str:
    """過去の検証：リスクの段階ごとに、実際に暴落が起きた割合。"""
    lines = ["<h2>予測はどのくらい当たるか</h2>"]
    rows = []
    for key, r in r_all.items():
        for kind, label in (("shock", "急落型"), ("bear", "長期下落型")):
            m = r["models"].get(kind)
            if not m or m["cv"].get("preds") is None:
                continue
            preds, y = m["cv"]["preds"], m["cv"]["y"]
            ratio = preds / m["base_rate"]
            bins = pd.cut(ratio, [-1, 0.8, 1.25, 2, 99], labels=RISK_WORDS)
            for w in RISK_WORDS:
                sel = y[bins == w]
                if len(sel) >= 12:
                    rows.append(f"<tr><td>{html.escape(config.MARKETS[key]['name'])}・{label}</td><td>{w}</td>"
                                f"<td>{sel.mean()*100:.0f}%</td><td>{len(sel)}か月分</td></tr>")
    if rows:
        lines.append('<p class="note">過去にさかのぼって予測し直し、「その後12か月以内に実際に暴落が起きた割合」を、リスクの段階ごとに集計したものです。'
                     '段階が上がるほど割合が増えていれば有効ですが、差が小さい段階は当てになりません。</p>'
                     f"<table><tr><th>対象</th><th>当時の段階</th><th>実際に暴落した割合</th><th>集計期間</th></tr>{''.join(rows)}</table>")
    if tr:
        if tr["n_scored"] == 0:
            first = tr["first"]
            when = (first + pd.DateOffset(months=config.HORIZON_MONTHS)).strftime("%Y年%m月") if first is not None else "-"
            lines.append(f'<p class="note"><b>毎日の予測の記録</b>：{tr["n_total"]}件を記録中です。最初の答え合わせは{when}以降にできます。</p>')
        else:
            rr = "".join(f"<tr><td>{x['market']}・{x['kind']}</td><td>{x['n']}</td><td>{x['predicted']*100:.0f}%</td><td>{x['actual']*100:.0f}%</td></tr>" for x in tr["rows"])
            lines.append(f"<p class='note'><b>毎日の予測の記録と答え合わせ</b></p><table><tr><th>対象</th><th>件数</th><th>予測の平均</th><th>実際の発生割合</th></tr>{rr}</table>")
    lines.append('<p class="note">結論：細かい数字は当てになりません。「平均より高いか低いか」の目安として見てください。</p>')
    return "".join(lines)


def build_html(results: dict, news: dict, demo: bool, tr: dict | None = None) -> str:
    body = [f"<h1>暴落モニター　{datetime.now():%Y-%m-%d}</h1>"]
    if demo:
        body.append('<div class="warn"><b>デモデータです。</b>数値は合成データによる動作確認用で、実際の市場とは無関係です。</div>')
    body.append('<div class="sum">' + "".join(_summary_box(k, r) for k, r in results.items()) + "</div>")
    body.append('<div class="warn">この表示だけで投資の判断はしないでください。暴落の「時期」は当てられません。'
                '信号は「過去の平均と比べて、いまが危うい状態か」の目安です。</div>')
    body.append(_track_record(results, tr))
    body.append("<h2>詳しい内容（見たいときだけ開く）</h2>")
    for k, r in results.items():
        body.append(f"<details><summary>{html.escape(config.MARKETS[k]['name'])} の詳細</summary>{_market_section(k, r)}</details>")
    body.append(f"<details><summary>ニュース・国政・地政学</summary>{_news_section(news)}</details>")
    return f"<!doctype html><html lang='ja'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>暴落モニター</title><style>{CSS}</style></head><body>{''.join(body)}</body></html>"
