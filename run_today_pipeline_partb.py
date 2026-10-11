import os
import subprocess

def git_commit_and_push():
    try:
        print("\nStep 2: Committing and pushing changes to Git...")
        subprocess.run(["git", "add", "."], check=False)
        res = subprocess.run(
            ["git", "commit", "-m", "Auto: Update multi-source (4 sources) prex and x post files"],
            capture_output=True,
            text=True
        )
        if res.returncode == 0:
            print("📦 Changes committed. Pushing to remote...")
            subprocess.run(["git", "push"], check=False)
            print("🚀 Successfully pushed to Git!")
        else:
            print("ℹ️ No changes to commit (working tree clean).")
    except Exception as e:
        print(f"Git sync error: {e}")

def main():
    print("=== Starting Scheduling & Sync Pipeline (Part B: Schedule & Git) ===")
    
    print("\nStep 1: Launching SocialDog Auto-Scheduler...")
    os.environ["DISPLAY"] = ":0"
    try:
        subprocess.run(["python3", "automation/socialdog_poster.py"], check=True)
        print("✅ SocialDog Poster executed successfully.")
    except subprocess.CalledProcessError as e:
        print(f"❌ Error during socialdog_poster.py execution: {e}")
        # 💡 2026-10-11: ここで即returnしていたため、socialdog_poster.pyが
        # 予約投稿自体は完了させた後にSIGTERM等で異常終了した場合でも
        # git_commit_and_push()が一切呼ばれず、その日のGit同期(アーカイブ移動・
        # 履歴ファイル更新)がまるごとスキップされる事故が発生した
        # (2026-10-08・2026-10-09の無人実行ログで確認)。失敗時でも、
        # そこまでに完了した分の変更は必ずGitに同期を試みるようにする
        print("⚠️ Continuing to Git sync so any work already done (scheduled posts, archived files) isn't left unsynced.")

    git_commit_and_push()
    print("\n✅ Pipeline execution (Part B) completed!")

if __name__ == "__main__":
    main()