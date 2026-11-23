"""設定。しきい値や対象市場はここだけ変えれば全体に反映される。"""
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
CACHE_DIR = DATA_DIR / "cache"      # 取得データのキャッシュ（1日で更新）
MANUAL_DIR = DATA_DIR / "manual"    # 手動CSV・ウォッチリスト置き場
OUT_DIR = ROOT / "output"

# ---- 対象市場 ----
MARKETS = {
    "US": {"name": "S&P500（米国）", "yahoo": "^GSPC", "stooq": "^spx"},
    "JP": {"name": "日経平均（日本）", "yahoo": "^N225", "stooq": "^nkx"},
}

# ---- FRED（無料・APIキー不要のCSV） ----
FRED_SERIES = {
    "GS10": "米10年国債利回り",
    "TB3MS": "米3か月国債利回り",
    "BAA": "米Baa社債利回り",
    "FEDFUNDS": "FF金利",
    "CPIAUCSL": "米消費者物価",
    "UNRATE": "米失業率",
    "DEXJPUS": "ドル円",
    "VIXCLS": "VIX（表示用。1990年以降）",
    # ダリオ型（債務サイクル）指標。FRED APIキーがあるときだけ取得される
    "GFDEGDQ188S": "米連邦政府債務/GDP",
    "CMDEBT": "米家計債務",
    "BCNSDODNS": "米非金融企業債務",
    "GDP": "米名目GDP",
    "NCBEILQ027S": "米非金融企業の株式時価総額（バフェット指標用）",
}

# FREDに繋がらないときのYahoo代替（利回り・ドル円・VIXのみ。社債利回り等は代替なし→その特徴量は自動的に外れる）
YAHOO_FALLBACK = {"GS10": "^TNX", "TB3MS": "^IRX", "DEXJPUS": "JPY=X", "VIXCLS": "^VIX"}

# ---- 暴落の定義 ----
BEAR_THRESHOLD = -0.20    # 高値から-20%（長期下落型）
SHOCK_THRESHOLD = -0.10   # 21営業日で-10%（急落型）
SHOCK_WINDOW = 21
SHOCK_MERGE_DAYS = 63     # この日数以内の急落は同じ事象とみなす

# ---- モデル ----
HORIZON_MONTHS = 12       # 詳細表示・ダリオ比較の基準期間
HORIZONS = [1, 3, 12]     # 短期・中期・長期（月）
LOGIT_C = 0.3             # 正則化（小さいほど強い）。事例が少ないため強めに設定
MIN_TRAIN_YEARS = 15
TEST_BLOCK_YEARS = 3
BOOTSTRAP_N = 200

# 市場ごとの特徴量（features.py の列名）
FEATURES = {
    "US": ["dd", "ret12", "vol3", "val", "curve", "credit", "ff_chg12", "cpi_yoy", "unrate_chg12"],
    "JP": ["dd", "ret12", "vol3", "val", "usdjpy_chg12", "curve", "credit", "ff_chg12"],
}
# バブル度の比較用に表示する過去の頂点（年月, 名称）
BUBBLE_PEAKS = {
    "US": [("1973-01", "1973年の高値"), ("1987-08", "ブラックマンデー前"), ("2000-03", "ITバブル頂点"),
           ("2007-10", "リーマン前"), ("2021-12", "コロナ後の高値")],
    "JP": [("1989-12", "バブル頂点"), ("2000-03", "ITバブル"), ("2007-07", "リーマン前"), ("2024-03", "2024年の高値")],
}

# ダリオ型の追加特徴量。通常版と検証成績を比べ、改善したときだけ採用する（米国のみ）
DALIO_EXTRA = {"US": ["gov_debt", "gov_debt_chg5", "priv_debt_chg5", "real_ff"]}

FEATURE_LABELS = {
    "gov_debt": "政府債務/GDP",
    "gov_debt_chg5": "政府債務/GDPの5年変化",
    "priv_debt_chg5": "民間債務/GDPの5年変化（信用の膨張）",
    "real_ff": "実質政策金利（FF金利−インフレ率）",
    "dd": "高値からの下落率",
    "ret12": "直近12か月の騰落率",
    "vol3": "直近3か月の変動率",
    "val": "割高度（10年平均比）",
    "curve": "米イールドカーブ（10年−3か月）",
    "credit": "米信用スプレッド（Baa−10年）",
    "ff_chg12": "FF金利の12か月変化",
    "cpi_yoy": "米インフレ率（前年比）",
    "unrate_chg12": "米失業率の12か月変化",
    "usdjpy_chg12": "ドル円の12か月変化",
}

# ---- ニュース（GDELT） ----
NEWS_QUERIES = {
    "市場不安": '("stock market crash" OR recession OR "financial crisis")',
    "通商・関税": '(tariff OR "trade war" OR sanctions)',
    "戦争・紛争": '(war OR "military conflict" OR missile attack)',
    "金融政策": '("rate hike" OR "central bank" OR inflation)',
}
