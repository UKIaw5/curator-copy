import requests
from typing import List, Dict

def fetch_reddit_posts(subreddits=["LocalLLaMA", "MachineLearning"], max_results=5) -> List[Dict[str, str]]:
    posts = []
    headers = {'User-Agent': 'Mozilla/5.0 (X11; Ubuntu; Linux x86_64) SourceCuratorBot/1.0'}
    
    for subreddit in subreddits:
        try:
            response = requests.get(f"https://www.reddit.com/r/{subreddit}/hot.json?limit={max_results}", headers=headers)
            response.raise_for_status()
            data = response.json()
            
            for item in data['data']['children']:
                post = {
                    'title': item['data']['title'],
                    'content': item['data'].get('selftext', ''),
                    'url': f"https://www.reddit.com{item['data']['permalink']}",
                    'source': "Reddit"
                }
                posts.append(post)
        
        except requests.exceptions.RequestException as e:
            print(f"Warning: Failed to fetch data from {subreddit}. Error: {e}")
    
    return posts

if __name__ == '__main__':
    import json
    normalized_posts = fetch_reddit_posts()
    print(json.dumps(normalized_posts, ensure_ascii=False, indent=4))