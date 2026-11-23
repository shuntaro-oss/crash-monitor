"""プッシュ通知（ntfy）。信号が「警戒」に変わった日だけ通知する。
環境変数 NTFY_TOPIC（GitHubのSecrets）が無ければ何もしない。"""
from __future__ import annotations

import json
import os
import sys
import urllib.request

import config

URL = "https://shuntaro-oss.github.io/crash-monitor/"
STATE = config.OUT_DIR / "state.json"


def _send(title: str, message: str, priority: int = 3) -> bool:
    topic = os.environ.get("NTFY_TOPIC")
    if not topic:
        print("[通知] NTFY_TOPIC が未設定のため送信しません")
        return False
    body = json.dumps({"topic": topic, "title": title, "message": message,
                       "priority": priority, "click": URL, "tags": ["warning"]}).encode("utf-8")
    req = urllib.request.Request("https://ntfy.sh/", data=body, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            print(f"[通知] 送信 {r.status}: {title}")
        return True
    except Exception as e:  # noqa: BLE001
        print(f"[通知] 送信失敗: {e}")
        return False


def check_and_notify(results: dict, signal_fn) -> None:
    """前回の信号と比べ、「警戒」になった/解除された時だけ通知する。"""
    prev = json.loads(STATE.read_text(encoding="utf-8")) if STATE.exists() else {}
    now = {}
    for key, r in results.items():
        word, _ = signal_fn(r)
        now[key] = word
        name = config.MARKETS[key]["name"]
        b = r.get("bubble", {}).get("level", "-")
        if word == "警戒" and prev.get(key) != "警戒":
            _send(f"暴落モニター：{name}が「警戒」", f"信号が「警戒」になりました（バブル度：{b}）。詳しくはページを確認してください。", 4)
        elif prev.get(key) == "警戒" and word != "警戒":
            _send(f"暴落モニター：{name}の警戒を解除", f"信号は「{word}」に下がりました。", 3)
    config.OUT_DIR.mkdir(exist_ok=True)
    STATE.write_text(json.dumps(now, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    if "--test" in sys.argv:
        _send("暴落モニター：通知テスト", "このメッセージが届けば、通知の設定は成功です。")
