import os
import shutil
import glob
import subprocess

def move_to_archive():
    print("\nStep 1: Archiving published X posts...")
    
    # Xポスト用のアーカイブ先
    x_archive_dir = "output/archive"
    os.makedirs(x_archive_dir, exist_ok=True)
    
    moved_any = False

    # X用ポストのみを対象に移動
    x_posts = glob.glob("output/output_x_posts_*.md")
    for file_path in x_posts:
        filename = os.path.basename(file_path)
        dest_path = os.path.join(x_archive_dir, filename)
        shutil.move(file_path, dest_path)
        print(f"📦 Moved X Post: {filename} -> {x_archive_dir}/")
        moved_any = True
        
    if not moved_any:
        print("ℹ️ No X post markdown files found to archive.")
    else:
        print("✅ Archiving completed.")

def git_commit_and_push():
    try:
        print("\nStep 2: Committing and pushing changes to Git...")
        subprocess.run(["git", "add", "."], check=False)
        
        res = subprocess.run(
            ["git", "commit", "-m", "Auto: Archive published X posts and sync history"],
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
    print("=== Starting Post-Publishing Sync Pipeline (Part B: X Posts) ===")
    
    print("⚠️ Xへの手動投稿は完了しましたか？")
    input("完了している場合は [Enter] キーを押してX用ファイルのアーカイブと同期を開始してください...")
    
    move_to_archive()
    git_commit_and_push()
    
    print("\n✅ X post-publishing tasks completed successfully!")

if __name__ == "__main__":
    main()
