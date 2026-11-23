import io, time, urllib.request
import pandas as pd
UA = {"User-Agent": "Mozilla/5.0 (crash-monitor probe)"}
def get(u):
    with urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=40) as r:
        return r.read().decode("utf-8", "replace")
h = get("https://www.multpl.com/shiller-pe/table/by-month")
t = pd.read_html(io.StringIO(h))[0]
print("[CAPE] 先頭", t.head(3).values.tolist(), "末尾", t.tail(2).values.tolist(), flush=True)
t2 = pd.read_html(io.StringIO(get("https://indexes.nikkei.co.jp/nkave/statistics/dataload?list=per&year=2025")))[0]
print("[PER2025] 形状", t2.shape, "列", list(t2.columns), flush=True)
print(t2.head(3).to_string(), flush=True); print(t2.tail(2).to_string(), flush=True)
t3 = pd.read_html(io.StringIO(get("https://indexes.nikkei.co.jp/nkave/statistics/dataload?list=per&year=2026")))[0]
print("[PER2026] 形状", t3.shape, "先頭", t3.head(2).values.tolist(), "末尾", t3.tail(2).values.tolist(), flush=True)
t4 = pd.read_html(io.StringIO(get("https://indexes.nikkei.co.jp/nkave/statistics/dataload?list=per&year=2004")))[0]
print("[PER2004] 形状", t4.shape, "先頭", t4.head(2).values.tolist(), flush=True)
