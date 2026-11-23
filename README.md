# 暴落モニター

過去の暴落・ショックの原因を指標で分析し、今後12か月以内の暴落確率を推定してHTMLレポートを出す。

## セットアップ
    pip install pandas numpy scikit-learn
    python main.py --demo      # まず合成データで動作確認
    python main.py --open      # 実データで実行しレポートを開く

オプション: `--markets US` / `--markets JP` / `--news`（ニュースも取得。既定はオフ。GitHub上では取得制限が出やすい）

## 出力
- `output/crash_report.html` … レポート（確率・要因・類似局面・過去の暴落と原因・ニュース）
- `output/summary.json` … 数値のみ（他ツール連携用）

## 仕組み
| 工程 | ファイル | 内容 |
|---|---|---|
| データ取得 | data.py | 株価=Yahoo→Stooq→手動CSV、マクロ=FRED。1日キャッシュ |
| 暴落検出 | events.py | 急落型(21営業日-10%)と長期下落型(高値-20%)を自動抽出。原因カタログは手動整理 |
| 特徴量 | features.py | 下落率・変動率・割高度・イールドカーブ・信用スプレッド・FF金利・インフレ・失業率・ドル円 |
| 確率 | model.py | ロジスティック回帰（強い正則化）。前進検証・ブートストラップ幅・要因分解・類似局面 |
| ニュース | news.py | GDELTのトーン悪化度＋手入力ウォッチリスト。モデル確率とは別枠 |
| 出力 | report.py | 単一HTML |

## カスタマイズ
- しきい値・特徴量・ニュース検索語は `config.py`
- 株価が取れないとき: `data/manual/US.csv` / `JP.csv`（`Date,Close`）を置く
- 要人発言・政策リスクの手入力: `data/manual/watchlist.json`
  `[{"item":"関税発表","severity":2,"note":"メモ"}]`（severityは0〜3）

## 限界
- 事例が少ない（-20%の局面は米国で10件前後）。確率は目安で、幅も必ず見る。
- ニュース・SNSは過去データと突き合わせていないため、確率には混ぜず補助表示。
- 原因カタログ(events.py)は手動整理。内容の確認と追記を推奨。
