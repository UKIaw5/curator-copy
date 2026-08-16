import requests
import json

def fetch_hacker_news(query="LLM OR AI", limit=5):
    url = f"https://hn.algolia.com/api/v1/search?query={query}&tags=story&hitsPerPage={limit}"
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        stories = []
        for hit in data.get('hits', []):
            title = hit.get('title', '')
            content = hit.get('story_text') or hit.get('title', '')
            url = hit.get('url', '')
            
            # Fallback to HN item URL if external URL is missing
            if not url:
                story_id = hit.get('objectID')
                url = f"https://news.ycombinator.com/item?id={story_id}"

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
    results = fetch_hacker_news()
    print(json.dumps(results, ensure_ascii=False, indent=2))