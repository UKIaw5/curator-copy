import os
import shutil
import json

def create_clean_template():
    # テンプレートを書き出す一時フォルダ名
    export_dir = "content-curator-template"
    
    # 1. 前回の抽出フォルダがあれば削除してリセット
    if os.path.exists(export_dir):
        shutil.rmtree(export_dir)
    os.makedirs(export_dir)

    # 2. 【ホワイトリスト】絶対に必須なコアディレクトリとファイル
    core_dirs = ["fetchers", "generators", "automation"]
    core_files = ["main.py", "run_pipeline.py", "run_today_pipeline_parta.py", "run_today_pipeline_partb.py", "run_today_pipeline_parta_rb.py", "requirements.txt", ".gitignore"]

    print("=== 抽出を開始します ===")

    # ディレクトリの抽出（__pycache__は除外）
    for d in core_dirs:
        if os.path.exists(d):
            print(f"📁 コピー中: {d}/")
            shutil.copytree(
                d, 
                os.path.join(export_dir, d),
                ignore=shutil.ignore_patterns('__pycache__', '*.pyc')
            )

    # ファイルの抽出
    for f in core_files:
        if os.path.exists(f):
            print(f"📄 コピー中: {f}")
            shutil.copy2(f, os.path.join(export_dir, f))

    # 3. outputフォルダのクリーンな状態（空枠）だけを作成
    print("✨ クリーンな output/ 構造を作成中...")
    os.makedirs(os.path.join(export_dir, "output", "raw"))
    os.makedirs(os.path.join(export_dir, "output", "archive"))
    
    # 空の history.json を作成（これがないと初回起動時にエラーになるため）
    with open(os.path.join(export_dir, "output", "history.json"), "w", encoding="utf-8") as f:
        json.dump([], f)

    # 4. ZIPに圧縮
    print("📦 ZIPファイルにパッケージング中...")
    shutil.make_archive(export_dir, 'zip', export_dir)

    # 5. 一時フォルダを削除（ZIPだけ残す）
    shutil.rmtree(export_dir)

    print(f"\n✅ 完了！ クリーンなテンプレートが '{export_dir}.zip' として保存されました。")

if __name__ == "__main__":
    create_clean_template()
