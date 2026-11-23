"""接続確認用（一時）。GitHub上で、各データ源に自動で届くかを調べて表示する。"""
import json, os, ssl, urllib.request

UA = {"User-Agent": "Mozilla/5.0 (crash-monitor probe)"}
URLS = [
    ("CAPE Yale xls", "http://www.econ.yale.edu/~shiller/data/ie_data.xls"),
    ("CAPE multpl", "https://www.multpl.com/shiller-pe/table/by-month"),
    ("PER multpl", "https://www.multpl.com/s-p-500-pe-ratio/table/by-month"),
    ("財務省 国債金利(英)", "https://www.mof.go.jp/english/policy/jgbs/reference/interest_rate/historical/jgbcme_all.csv"),
    ("財務省 国債金利(和)", "https://www.mof.go.jp/jgbs/reference/interest_rate/historical/jgbcme_all.csv"),
    ("日経 指標ページ", "https://indexes.nikkei.co.jp/nkave/archives/data"),
    ("日経 英語ページ", "https://indexes.nikkei.co.jp/en/nkave/archives/data"),
    ("日経 プロフィル", "https://indexes.nikkei.co.jp/nkave/index/profile?idx=nk225"),
    ("JPX PER/PBR", "https://www.jpx.co.jp/markets/statistics-equities/misc/04.html"),
    ("日銀 時系列", "https://www.stat-search.boj.or.jp/index.html"),
]
for name, url in URLS:
    try:
        req = urllib.request.Request(url, headers=UA)
        with urllib.request.urlopen(req, timeout=30) as r:
            b = r.read(400000)
            head = b[:160].decode("utf-8", "replace").replace("\n", " ")
            print(f"[OK ] {name} status={r.status} type={r.headers.get('Content-Type')} bytes>={len(b)} head={head!r}", flush=True)
    except Exception as e:
        print(f"[NG ] {name} {type(e).__name__}: {str(e)[:120]}", flush=True)

key = os.environ.get("FRED_API_KEY")
for sid in ["IRLTLT01JPM156N", "IR3TIB01JPM156N", "JPNCPIALLMINMEI", "GGGDTAJPA188N", "LRUN64TTJPM156S", "CPGRLE01JPM659N"]:
    try:
        u = f"https://api.stlouisfed.org/fred/series/observations?series_id={sid}&api_key={key}&file_type=json"
        with urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=30) as r:
            o = [x for x in json.loads(r.read())["observations"] if x["value"] != "."]
            print(f"[OK ] FRED {sid} 件数={len(o)} 最初={o[0]['date']} 最後={o[-1]['date']}", flush=True)
    except Exception as e:
        print(f"[NG ] FRED {sid} {type(e).__name__}: {str(e)[:100]}", flush=True)
