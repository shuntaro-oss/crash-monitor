"""暴落モニター 実行本体。

使い方:
    python main.py                 # 実データで実行（米・日、ニュースあり）
    python main.py --markets US    # 米国のみ
    python main.py --no-news       # ニュース取得を省略（約1分短縮）
    python main.py --demo          # 合成データで動作確認
"""
from __future__ import annotations

import argparse
import json
import sys
import webbrowser

import config
import data
import events as ev
import features
import model
import news as newsmod
import bubble
import report


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--markets", nargs="+", default=list(config.MARKETS), choices=list(config.MARKETS))
    ap.add_argument("--no-news", action="store_true")
    ap.add_argument("--demo", action="store_true")
    ap.add_argument("--open", action="store_true", help="完了後にレポートをブラウザで開く")
    a = ap.parse_args()

    if a.demo:
        from demo_data import make_demo
        d = make_demo()
    else:
        print("データ取得中...")
        d = data.load_all(a.markets)

    news = newsmod.news_stress(enabled=not (a.no_news or a.demo))

    results = {}
    for key in a.markets:
        print(f"[{key}] 分析中...")
        px = d["px"][key]
        events = ev.attach_causes(
            __import__("pandas").concat([ev.find_bear_episodes(px), ev.find_shock_episodes(px)],
                                        ignore_index=True), key)
        feat = features.build_features(px, d["fred"])
        res = {"events": events, "models": {}, "errors": {}, "news_score": news["score"]}
        for kind in ("shock", "bear"):
            sub = events[events["kind"] == kind]
            try:
                base = model.analyze(feat, sub, config.FEATURES[key], kind)
                res["models"][kind] = base
                extra = [c for c in config.DALIO_EXTRA.get(key, []) if c in feat.columns and feat[c].notna().sum() > 240]
                if extra:
                    try:
                        ext = model.analyze(feat, sub, config.FEATURES[key] + extra, kind)
                        b, e = base["cv"], ext["cv"]
                        adopt = (None not in (b["auc"], e["auc"]) and e["brier"] < b["brier"] and e["auc"] >= b["auc"])
                        res.setdefault("compare", {})[kind] = {"base": b, "ext": e, "extra": extra, "adopt": adopt,
                                                              "p_base": base["p_now"], "p_ext": ext["p_now"]}
                        if adopt:
                            res["models"][kind] = ext
                        print(f"  {key}/{kind}: ダリオ版 AUC {e['auc']} Brier {e['brier']} / 通常版 AUC {b['auc']} Brier {b['brier']} -> {'採用' if adopt else '不採用'}")
                    except Exception as ex:  # noqa: BLE001
                        print(f"  [ダリオ版スキップ] {key}/{kind}: {ex}")
            except Exception as e:  # noqa: BLE001
                res["errors"][kind] = str(e)
                print(f"  [警告] {key}/{kind}: {e}")
        try:
            res["bubble"] = bubble.compute(feat, key)
        except Exception as e:  # noqa: BLE001
            print(f"  [警告] バブル度 {key}: {e}")
        results[key] = res

    config.OUT_DIR.mkdir(exist_ok=True)
    suffix = "_demo" if a.demo else ""
    out = config.OUT_DIR / f"crash_report{suffix}.html"
    out.write_text(report.build_html(results, news, a.demo), encoding="utf-8")

    summary = {k: {kind: {"p": m["p_now"], "lo": m["p_lo"], "hi": m["p_hi"], "base": m["base_rate"],
                          "asof": str(m["asof"].date())} for kind, m in r["models"].items()}
               for k, r in results.items()}
    for k, r in results.items():
        if "bubble" in r:
            summary[k]["bubble"] = {"score": r["bubble"]["score"], "level": r["bubble"]["level"]}
    summary["news_score"] = news["score"]
    (config.OUT_DIR / f"summary{suffix}.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    names = {"shock": "急落型(21営業日で-10%)", "bear": "長期下落型(高値から-20%)"}
    md = [f"# 暴落モニター {__import__('datetime').date.today()}", ""]
    for k, r in summary.items():
        if k == "news_score":
            continue
        md.append(f"## {config.MARKETS[k]['name']}")
        for kind, m in r.items():
            if kind == "bubble":
                md.append(f"- バブル度: **{m['score']:.0f}/100（{m['level']}）**")
                continue
            md.append(f"- {names[kind]}: **{m['p']*100:.1f}%**（幅 {m['lo']*100:.1f}〜{m['hi']*100:.1f}%、過去平均 {m['base']*100:.1f}%、基準日 {m['asof']}）")
        md.append("")
    md.append(f"ニュース不安度: {summary['news_score'] if summary['news_score'] is None else round(summary['news_score'])} / 100")
    (config.OUT_DIR / f"latest{suffix}.md").write_text("\n".join(md), encoding="utf-8")
    print(f"完了: {out}")
    for k, r in summary.items():
        print(k, r)
    if a.open:
        webbrowser.open(out.as_uri())
    return 0


if __name__ == "__main__":
    sys.exit(main())
