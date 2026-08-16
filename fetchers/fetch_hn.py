import requests
import json

def fetch_hn_stories(query="LLM OR AI", max_results=10):
    url = f"https://hn.algolia.com/api/v1/search?query={query}&tags=story&hitsPerPage={max_results}"
    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        
        stories = []
        for hit in data.get('hits', []):
            title = hit.get('title', '')
            content = hit.get('story_text') or hit.get('title', '')
            url = hit.get('url', '')
            stories.append({
                'title': title,
                'content': content,
                'url': url,
                'source': "Hacker News"
            })
        
        return stories
    except (requests.RequestException, json.JSONDecodeError) as e:
        print(f"Warning: Failed to fetch Hacker News stories - {e}")
        return []

if __name__ == '__main__':
    results = fetch_hn_stories()
    print(json.dumps(results, ensure_ascii=False, indent=2))