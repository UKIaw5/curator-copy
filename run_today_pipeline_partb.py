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
    
    print("\nStep 1: Launching X Auto-Scheduler...")
    os.environ["DISPLAY"] = ":0"
    try:
        subprocess.run(["python3", "automation/x_poster.py"], check=True)
        print("✅ X Poster executed successfully.")
    except subprocess.CalledProcessError as e:
        print(f"❌ Error during x_poster.py execution: {e}")
        return

    git_commit_and_push()
    print("\n✅ Pipeline execution (Part B) completed!")

if __name__ == "__main__":
    main()