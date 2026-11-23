"""接続確認用（一時）その2：データの場所と形式を調べる。"""
import io, re, urllib.request, urllib.parse

UA = {"User-Agent": "Mozilla/5.0 (crash-monitor probe)"}
def get(u, n=3_000_000):
    with urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=40) as r:
        return r.read(n)

# 1) Shiller xls の構造
try:
    import pandas as pd
    raw = get("http://www.econ.yale.edu/~shiller/data/ie_data.xls", 20_000_000)
    x = pd.ExcelFile(io.BytesIO(raw))
    print("[Shiller] シート:", x.sheet_names, flush=True)
    df = x.parse("Data", header=None)
    print("[Shiller] 形状:", df.shape, flush=True)
    for i in range(0, 9):
        print("[Shiller] 行", i, [str(v)[:14] for v in df.iloc[i].tolist()[:16]], flush=True)
    for i in (len(df) - 4, len(df) - 3, len(df) - 2, len(df) - 1):
        print("[Shiller] 末尾", i, [str(v)[:10] for v in df.iloc[i].tolist()[:14]], flush=True)
except Exception as e:
    print("[Shiller NG]", type(e).__name__, str(e)[:200], flush=True)

# 2) 日経・JPXのページ内のデータ関連リンク
pages = ["https://indexes.nikkei.co.jp/nkave/archives/data",
         "https://indexes.nikkei.co.jp/nkave/index/profile?idx=nk225",
         "https://www.jpx.co.jp/markets/statistics-equities/misc/04.html"]
for p in pages:
    try:
        h = get(p).decode("utf-8", "replace")
        links = set(re.findall(r'(?:href|src|action)="([^"]+)"', h))
        keep = [l for l in links if re.search(r'csv|xls|download|dataload|per|pbr|historical|archives', l, re.I)]
        print(f"[Links] {p} 全リンク{len(links)} 該当{len(keep)}", flush=True)
        for l in sorted(keep)[:40]:
            print("   ", urllib.parse.urljoin(p, l)[:160], flush=True)
        for m in re.finditer(r'(PER|予想PER|株価収益率)', h):
            seg = re.sub(r'<[^>]+>', ' ', h[max(0, m.start()-80):m.end()+160])
            print("   [文脈]", re.sub(r'\s+', ' ', seg)[:200], flush=True)
            break
    except Exception as e:
        print(f"[Links NG] {p} {type(e).__name__}: {str(e)[:100]}", flush=True)
