import glob
import json
import os
import re

HISTORY_FILE = "output/history.json"

def extract_urls_from_files(file_paths):
    urls = set()
    url_pattern = re.compile(r'https?://[^\s<>"\\\)\]]+')
    for path in file_paths:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
                found = url_pattern.findall(content)
                for u in found:
                    # 末尾の記号ノイズを除去
                    clean_u = re.sub(r"[\.\,\)\*\_\:]+$", "", u)
                    urls.add(clean_u)
    return urls

def main():
    print("=== Migrating to File-System Driven History ===")
    
    # アーカイブ済みのファイルからURLを抽出（これが「絶対に二度と取得しない」真の完了リスト）
    archived_files = glob.glob("output/archive/*.md")
    published_urls = extract_urls_from_files(archived_files)
    
    # 今後の拡張性を考慮して dict 型で保存
    history_data = {}
    for url in published_urls:
        history_data[url] = {"status": "published"}

    # outputフォルダがなければ作成
    os.makedirs("output", exist_ok=True)

    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history_data, f, ensure_ascii=False, indent=4)

    print(f"✅ Migration Completed!")
    print(f" - Published (アーカイブ済みで今後スキップされる記事): {len(published_urls)} items")
    print(f"💾 Saved to `{HISTORY_FILE}`")
    print("\n💡 これで古い seen_urls.json は不要になりました。削除してOKです！")

if __name__ == "__main__":
    main()
