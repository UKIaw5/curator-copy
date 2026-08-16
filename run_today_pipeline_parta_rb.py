import os
import glob
import shutil

# 💡 こちらも本丸のファイルパスに変更
HISTORY_FILE = "output/seen_urls.json"
HISTORY_BAK = "output/seen_urls.json.bak"

def main():
    print("=== Reverting Latest Part A Execution ===")
    
    files_to_delete = []
    
    # 1. 削除対象のMDファイルを特定
    raw_files = sorted(glob.glob("output/raw/output_prex_posts_*.md"))
    if raw_files:
        latest_raw = raw_files[-1]
        files_to_delete.append(latest_raw)
        
        base_name = os.path.basename(latest_raw)
        timestamp = base_name.replace("output_prex_posts_", "").replace(".md", "")
        refined_file = f"output/output_x_posts_{timestamp}.md"
        
        if os.path.exists(refined_file):
            files_to_delete.append(refined_file)

    if not files_to_delete:
        print("ℹ️ No output files found to delete.")
    else:
        print("\n⚠️ The following generated files will be DELETED:")
        for f in files_to_delete:
            print(f" - {f}")

    # 2. 履歴復元の確認
    print(f"\n⚠️ `{HISTORY_FILE}` will be restored from backup.")
    
    confirm = input("\nAre you sure you want to rollback? (y/n): ")
    if confirm.lower() == 'y':
        # ファイル削除
        for f in files_to_delete:
            try:
                os.remove(f)
                print(f"🗑️ Deleted: {f}")
            except Exception as e:
                print(f"❌ Failed to delete {f}: {e}")
        
        # 履歴の復元
        if os.path.exists(HISTORY_BAK):
            try:
                shutil.copy2(HISTORY_BAK, HISTORY_FILE)
                print(f"🔄 Restored history from {HISTORY_BAK}.")
            except Exception as e:
                print(f"❌ Failed to restore history: {e}")
        else:
            print("⚠️ No history backup found. History might not be reverted.")
            
        print("\n✅ Rollback complete! You can tune your code/prompts and run Part A again.")
    else:
        print("\n🚫 Rollback cancelled.")

if __name__ == "__main__":
    main()