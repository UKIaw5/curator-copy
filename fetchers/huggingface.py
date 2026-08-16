import urllib.request
import json

def fetch_huggingface_papers(limit=10):
    url = "https://huggingface.co/api/daily_papers"
    stories = []
    
    try:
        req = urllib.request.Request(
            url, 
            headers={"User-Agent": "Mozilla/5.0"}
        )
        with urllib.request.urlopen(req, timeout=10) as response:
            papers = json.loads(response.read().decode('utf-8'))
            
        for paper_entry in papers[:limit]:
            paper = paper_entry.get("paper", {})
            title = paper.get("title", "No Title")
            summary = paper.get("summary", "No Summary")
            
            # Try to get paper ID from 'id' or '_id'
            paper_id = paper.get("id") or paper.get("_id", "")
            
            # Generate unique URL for the paper
            if paper_id:
                paper_url = f"https://huggingface.co/papers/{paper_id}"
            else:
                paper_url = "https://huggingface.co/papers"
            
            stories.append({
                'title': f"HF Paper: {title}",
                'content': summary.strip().replace("\n", " "),
                'url': paper_url,
                'source': "Hugging Face Daily Papers"
            })
            
    except Exception as e:
        print(f"Warning: Failed to fetch Hugging Face Papers - {e}")
        
    return stories

if __name__ == '__main__':
    results = fetch_huggingface_papers(limit=10)
    print(json.dumps(results, ensure_ascii=False, indent=2))