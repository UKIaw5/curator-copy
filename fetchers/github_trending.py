import urllib.request
import json
from datetime import datetime, timedelta

def fetch_github_trending(limit=10):
    target_date = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
    url = f"https://api.github.com/search/repositories?q=created:>{target_date}&sort=stars&order=desc"
    stories = []
    
    try:
        req = urllib.request.Request(
            url, 
            headers={
                "User-Agent": "Mozilla/5.0",
                "Accept": "application/vnd.github.v3+json"
            }
        )
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode('utf-8'))
            
        items = data.get("items", [])
        for item in items[:limit]:
            name = item.get("full_name", "No Name")
            description = item.get("description") or "No description provided."
            html_url = item.get("html_url", "")
            
            stories.append({
                'title': f"GitHub Trending: {name}",
                'content': description.strip().replace("\n", " "),
                'url': html_url,
                'source': "GitHub Trending"
            })
            
    except Exception as e:
        print(f"Warning: Failed to fetch GitHub Trending - {e}")
        
    return stories

if __name__ == '__main__':
    results = fetch_github_trending(limit=10)
    print(json.dumps(results, ensure_ascii=False, indent=2))
