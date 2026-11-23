import io, re, urllib.request
import pandas as pd
UA = {"User-Agent": "Mozilla/5.0 (crash-monitor probe)"}
def get(u):
    with urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=40) as r:
        return r.read().decode("utf-8", "replace")
h = get("https://indexes.nikkei.co.jp/nkave/archives/data?list=per")
for m in re.finditer(r"dataload", h):
    print("[JS文脈]", re.sub(r"\s+", " ", h[max(0, m.start()-250):m.end()+250]), flush=True)
    print("-----", flush=True)
for m in re.finditer(r"<(?:select|option|input)[^>]*(?:month|year)[^>]*>", h, re.I):
    print("[フォーム]", m.group(0)[:200], flush=True)
base = "https://indexes.nikkei.co.jp/nkave/statistics/dataload?list=per"
for q in ["&year=2025&month=3", "&year=2025&month=03", "&year=2025&m=3", "&year=2025&mon=3", "&year=2025&type=month&month=3"]:
    try:
        t = pd.read_html(io.StringIO(get(base + q)))[0]
        print(f"[試行] {q} 形状={t.shape} 先頭={t.head(1).values.tolist()} 末尾={t.tail(1).values.tolist()}", flush=True)
    except Exception as e:
        print(f"[試行NG] {q} {type(e).__name__}", flush=True)
