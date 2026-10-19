"""
SocialDogセッションCookieの期限切れが近づいていたらDiscordへ単発通知する。

日次の実行結果レポート(notify_daily_result.py)とは独立したスクリプト。
Windowsタスクスケジューラから毎日正午に実行される想定(README/CLAUDE.md参照)。
期限が十分残っている日は何も送らない(「単発の通知」であり毎日のレポートではないため)。

2026-10-19に、SocialDogのセッションCookie失効に誰も気づかないままX投稿が0件に
なった事故をきっかけに導入した。
"""
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from notify_daily_result import load_env_file, post_to_discord, ENV_FILE

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
COOKIE_FILE = os.path.join(REPO_ROOT, "automation", "socialdog_cookies.json")
COOKIE_NAME = "socialdogSessionV2"
WARN_DAYS = 2


def find_session_cookie_expiry():
    """Cookieファイルからセッションcookieの有効期限(epoch秒)を返す。
    ファイルが無い/壊れている/対象cookieが無い場合はNoneを返す(「期限不明」として
    安全側＝要警告に倒すため、呼び出し側でNoneも警告対象として扱う)。"""
    if not os.path.exists(COOKIE_FILE):
        return None
    try:
        with open(COOKIE_FILE, encoding="utf-8") as f:
            cookies = json.load(f)
    except (json.JSONDecodeError, OSError):
        return None

    for c in cookies:
        if c.get("name") == COOKIE_NAME:
            return c.get("expirationDate") or c.get("expires")
    return None


# 💡 日報(notify_daily_result.py)と同じpost_to_discord()を使い回すと、Discord上で
# 埋め込みのタイトル・色が「curator-copy 日次実行レポート」(日報と同じ)になり、
# 毎日届く日報に紛れて見逃される事故が実際にあった(2026-10-19、ユーザー報告)。
# ここでは緊急度に応じて専用のタイトル・色(赤=要即対応、オレンジ=もうすぐ)を
# 付け、日報と一目で見分けられるようにしている。本文は固定テンプレートのまま
# (LLM生成ではない。生成コストを払う理由が無いため)
COLOR_RED = 15158332     # 0xE74C3C: 既に期限切れ / 状態不明(=要即対応)
COLOR_ORANGE = 15105570  # 0xE67E22: あと数日で期限切れ(=そろそろ対応)


def main():
    force_test = "--test" in sys.argv
    expiry = find_session_cookie_expiry()
    now = time.time()

    if expiry is None:
        title = "⚠️⚠️⚠️ SocialDog Cookieが見つかりません！"
        color = COLOR_RED
        message = (
            "**SocialDogのセッションCookieが読み取れませんでした。**\n"
            "`automation/socialdog_cookies.json` が無いか壊れている可能性があります。\n"
            "このままだとX投稿が予約されません。cookie-editorでweb.social-dog.netから"
            "取得し直して配置してください。"
        )
    else:
        days_left = (expiry - now) / 86400
        if days_left > WARN_DAYS and not force_test:
            print(f"OK: socialdogSessionV2 expires in {days_left:.1f} day(s). No notification needed.")
            return
        expiry_str = time.strftime("%Y-%m-%d %H:%M", time.localtime(expiry))
        if days_left < 0:
            title = "⚠️⚠️⚠️ SocialDog連携、切れとるで！！"
            color = COLOR_RED
            message = (
                f"**SocialDogのセッションCookieが既に期限切れです**({expiry_str}に失効)。\n"
                "このままだとX投稿が予約されません。cookie-editorでweb.social-dog.netから"
                "取得し直し、`automation/socialdog_cookies.json` を更新してください。"
            )
        else:
            title = "⚠️⚠️⚠️ SocialDog Cookie、もうすぐ切れるで！"
            color = COLOR_ORANGE
            message = (
                f"**SocialDogのセッションCookieがあと{days_left:.1f}日で期限切れになります**"
                f"({expiry_str}に失効予定)。\n"
                "切れる前にcookie-editorでweb.social-dog.netから取得し直し、"
                "`automation/socialdog_cookies.json` を更新してください。"
            )

    if force_test:
        title = "🧪 " + title + "(テスト通知)"

    print(f"{title}\n{message}")
    env = load_env_file(ENV_FILE)
    webhook_url = os.environ.get("DISCORD_WEBHOOK_URL") or env.get("DISCORD_WEBHOOK_URL")
    post_to_discord(webhook_url, message, title=title, color=color)


if __name__ == "__main__":
    main()
