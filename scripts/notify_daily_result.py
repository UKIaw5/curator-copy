"""
daily_auto_run.sh の最後に呼ばれる通知ステップ。

その日のログファイルからサマリーを作り、
1. Discord Webhook に投稿する
2. Windowsのメモ帳(Notepad)でその場で開く(PCの前にいれば確実に見える)

どちらかが失敗しても(Webhook未設定、Windows側呼び出し失敗等)、
daily_auto_run.sh 本体の成否には影響させない(常に正常終了する)。
"""
import glob
import os
import re
import subprocess

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG_DIR = os.path.join(REPO_ROOT, "output", "daily_auto_logs")
ENV_FILE = os.path.join(REPO_ROOT, ".env")


def load_env_file(path):
    env = {}
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip()
    return env


def get_latest_log():
    logs = sorted(glob.glob(os.path.join(LOG_DIR, "*.log")), key=os.path.getmtime)
    return logs[-1] if logs else None


def build_report(log_path):
    if not log_path:
        return "⚠️ 本日のログファイルが見つかりませんでした。daily_auto_run.shが実行されたか確認してください。"

    with open(log_path, encoding="utf-8") as f:
        content = f.read()

    x_scheduled = re.findall(r"✅ Scheduled for ([^!]+)!", content)
    note_success_count = content.count("🎉 Article successfully posted as FREE")
    errors = [
        line.strip()
        for line in content.splitlines()
        if "❌" in line or re.search(r"\berror\b", line, re.IGNORECASE)
    ]

    report_marker = "--- Step 6: Final report"
    report_start = content.find(report_marker)
    final_report_block = content[report_start:].strip() if report_start != -1 else ""
    # "=== Daily Auto Run finished" 以降は不要なので切り落とす
    end_marker = "=== Daily Auto Run finished"
    end_idx = final_report_block.find(end_marker)
    if end_idx != -1:
        final_report_block = final_report_block[:end_idx].strip()

    parts = [
        f"📅 curator-copy 日次実行レポート",
        f"ログ: {os.path.basename(log_path)}",
        "",
        f"🐦 X投稿: {len(x_scheduled)}件 予約",
    ]
    for t in x_scheduled:
        parts.append(f"   - {t.strip()}")

    parts.append("")
    parts.append(f"📝 note.com: {note_success_count}件 公開")

    if final_report_block:
        parts.append("")
        parts.append(final_report_block[:1500])

    if errors:
        parts.append("")
        parts.append(f"⚠️ エラー/❌行が{len(errors)}件検出されました(抜粋):")
        for e in errors[:5]:
            parts.append(f"   {e[:200]}")

    return "\n".join(parts)


def post_to_discord(webhook_url, report_text):
    if not webhook_url:
        print("⚠️ DISCORD_WEBHOOK_URL not set in .env, skipping Discord notification.")
        return
    try:
        import requests
        payload = {
            "username": "post done!",
            "embeds": [
                {
                    "title": "curator-copy 日次実行レポート",
                    "description": report_text[:4000],
                    "color": 5763719,
                }
            ],
        }
        res = requests.post(webhook_url, json=payload, timeout=15)
        if res.status_code >= 300:
            print(f"⚠️ Discord notification failed: {res.status_code} {res.text[:200]}")
        else:
            print("✅ Discord notification sent.")
    except Exception as e:
        print(f"⚠️ Discord notification error: {e}")


def open_in_notepad(report_text):
    """💡 \\\\wsl.localhost\\...のUNCパスで直接notepad.exeを起動すると、
    Windows 11の新Notepad(UWPサンドボックス版)がUNCパスのファイルオープンに
    失敗し、空のウィンドウが開くだけになる実例を確認した(2026-10-08)。
    Windows側のローカルパス(%TEMP%配下)にファイルを書き出してから、
    そのWindowsパスで起動することで回避する。"""
    try:
        temp_win = subprocess.run(
            ["cmd.exe", "/c", "echo %TEMP%"],
            capture_output=True, text=True, timeout=15
        ).stdout.strip()
        if not temp_win:
            print("⚠️ Could not resolve Windows TEMP dir, skipping Notepad launch.")
            return

        temp_wsl = subprocess.run(
            ["wslpath", "-u", temp_win],
            capture_output=True, text=True, timeout=15
        ).stdout.strip()

        report_path_wsl = os.path.join(temp_wsl, "curator_daily_report.txt")
        with open(report_path_wsl, "w", encoding="utf-8") as f:
            f.write(report_text)

        report_path_win = temp_win + "\\curator_daily_report.txt"
        # 💡 start_new_session=True + DEVNULLへのリダイレクトで完全にデタッチする。
        # cmd.exe /c start 経由だとWSL interopがGUIプロセスの終了を待って
        # ブロックする実例を確認したため、notepad.exeを直接起動する
        subprocess.Popen(
            ["notepad.exe", report_path_win],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        print(f"✅ Opened report in Notepad: {report_path_win}")
    except Exception as e:
        print(f"⚠️ Failed to open Notepad: {e}")


def main():
    env = load_env_file(ENV_FILE)
    webhook_url = os.environ.get("DISCORD_WEBHOOK_URL") or env.get("DISCORD_WEBHOOK_URL")

    log_path = get_latest_log()
    report_text = build_report(log_path)

    print("\n--- Notification report content ---")
    print(report_text)
    print("--- end ---\n")

    post_to_discord(webhook_url, report_text)
    open_in_notepad(report_text)


if __name__ == "__main__":
    main()
