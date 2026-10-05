import os
import glob
import shutil
import json
import re

HISTORY_FILE = "output/seen_urls.json"
HISTORY_BAK = "output/seen_urls.json.bak"

def extract_urls_from_file(filepath):
    """MarkdownファイルからURLを抽出する"""
    urls = set()
    if not os.path.exists(filepath):
        return urls
    
    url_pattern = re.compile(r'https?://[^\s\)\]\>]+')
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
            found = url_pattern.findall(content)
            urls.update(found)
    except Exception as e:
        print(f"⚠️ Failed to read {filepath} for URL extraction: {e}")
        
    return urls

def main():
    print("=== Reverting Latest Part A Execution ===")
    
    files_to_delete = []
    target_urls_to_remove = set()
    
    # 1. 削除対象のMDファイルを特定
    raw_files = sorted(glob.glob("output/raw/output_prex_posts_*.md"))
    if raw_files:
        latest_raw = raw_files[-1]
        files_to_delete.append(latest_raw)
        
        # 削除予定のファイルからURLを収集（バックアップが無い場合の保険）
        target_urls_to_remove.update(extract_urls_from_file(latest_raw))
        
        base_name = os.path.basename(latest_raw)
        timestamp = base_name.replace("output_prex_posts_", "").replace(".md", "")
        refined_file = f"output/output_x_posts_{timestamp}.md"
        
        if os.path.exists(refined_file):
            files_to_delete.append(refined_file)

    if not files_to_delete:
        print("ℹ️ No output files found to delete.")
        return

    print("\n⚠️ Target files to remove:")
    for f in files_to_delete:
        print(f" - {f}")

    # 2. 履歴の復元（第一優先: .bak から復元、第二優先: JSONから直接該当URLを削除）
    if os.path.exists(HISTORY_BAK):
        try:
            shutil.copy2(HISTORY_BAK, HISTORY_FILE)
            print(f"🔄 Restored history from backup: {HISTORY_BAK}")
        except Exception as e:
            print(f"❌ Failed to restore history from backup: {e}")
    else:
        print("⚠️ No history backup found (.bak). Falling back to URL targeted removal...")
        if os.path.exists(HISTORY_FILE) and target_urls_to_remove:
            try:
                with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                    seen_urls = json.load(f)
                
                before_count = len(seen_urls)
                # リスト/セット両対応でURL除外
                if isinstance(seen_urls, list):
                    updated_urls = [u for u in seen_urls if u not in target_urls_to_remove]
                elif isinstance(seen_urls, dict):
                    updated_urls = {k: v for k, v in seen_urls.items() if k not in target_urls_to_remove}
                else:
                    updated_urls = seen_urls

                removed_count = before_count - len(updated_urls)
                
                with open(HISTORY_FILE, "w", encoding="utf-8") as f:
                    json.dump(updated_urls, f, ensure_ascii=False, indent=2)
                
                print(f"🧹 Successfully purged {removed_count} URLs from {HISTORY_FILE}.")
            except Exception as e:
                print(f"❌ Failed to purge URLs from history: {e}")

    # 3. ファイル削除の実行
    print("\n🗑️ Deleting generated files:")
    for f in files_to_delete:
        try:
            os.remove(f)
            print(f" - Deleted: {f}")
        except Exception as e:
            print(f"❌ Failed to delete {f}: {e}")
        
    print("\n✅ Rollback complete! Your environment is clean and ready to re-run.")

if __name__ == "__main__":
    main()