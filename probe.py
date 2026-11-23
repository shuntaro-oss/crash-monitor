"""接続確認その3：最新のCAPE取得先と、日経PERの取得方法。"""
import io, re, urllib.request, urllib.parse
import pandas as pd
UA = {"User-Agent": "Mozilla/5.0 (crash-monitor probe)"}
def get(u, n=5_000_000):
    with urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=40) as r:
        return r.read(n)

# 1) multpl のCAPE表
try:
    h = get("https://www.multpl.com/shiller-pe/table/by-month").decode("utf-8", "replace")
    t = pd.read_html(io.StringIO(h))[0]
    print("[multpl CAPE] 形状", t.shape, "列", list(t.columns), flush=True)
    print(t.head(4).to_string(), flush=True); print(t.tail(2).to_string(), flush=True)
except Exception as e:
    print("[multpl NG]", type(e).__name__, str(e)[:200], flush=True)

# 2) 日経PERページ
for u in ["https://indexes.nikkei.co.jp/nkave/archives/data?list=per",
          "https://indexes.nikkei.co.jp/nkave/archives/data?list=pbr"]:
    try:
        h = get(u).decode("utf-8", "replace")
        txt = re.sub(r"<script.*?</script>|<style.*?</style>", " ", h, flags=re.S)
        txt = re.sub(r"<[^>]+>", " ", txt); txt = re.sub(r"\s+", " ", txt)
        i = txt.find("PER")
        print(f"[日経] {u[-8:]} 本文抜粋:", txt[max(i-60, 0):i+900], flush=True)
        for m in re.findall(r"(?:dataload|download|csv)[^\"' <>]{0,120}", h)[:12]:
            print("   [手がかり]", m, flush=True)
        tabs = pd.read_html(io.StringIO(h))
        print("   [表の数]", len(tabs), [t.shape for t in tabs][:5], flush=True)
        if tabs:
            print(tabs[0].head(3).to_string()[:500], flush=True)
    except Exception as e:
        print("[日経 NG]", u[-8:], type(e).__name__, str(e)[:160], flush=True)

# 3) 日経 dataload のパラメータ推測
for q in ["list=per", "list=per&year=2025", "list=per&type=monthly", "list=per&term=all"]:
    u = "https://indexes.nikkei.co.jp/nkave/statistics/dataload?" + q
    try:
        b = get(u, 400000)
        print(f"[dataload] {q} bytes={len(b)} head={b[:220].decode('utf-8','replace')!r}", flush=True)
    except Exception as e:
        print(f"[dataload NG] {q} {type(e).__name__}: {str(e)[:90]}", flush=True)

# 4) 日経平均の日次CSV（公式）
try:
    b = get("https://indexes.nikkei.co.jp/nkave/historical/nikkei_stock_average_daily_jp.csv", 3_000_000)
    print("[日経日次CSV] bytes", len(b), b[:200].decode("cp932", "replace")[:200].replace("\n", " "), flush=True)
except Exception as e:
    print("[日経日次CSV NG]", e, flush=True)

# 5) 財務省 国債金利CSVの構造
b = get("https://www.mof.go.jp/english/policy/jgbs/reference/interest_rate/historical/jgbcme_all.csv", 9_000_000)
df = pd.read_csv(io.BytesIO(b), skiprows=1)
print("[JGB] 形状", df.shape, list(df.columns)[:6], "最終行", df.iloc[-1].tolist()[:4], flush=True)
