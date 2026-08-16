import urllib.request
import xml.etree.ElementTree as ET

def fetch_arxiv(category="cs.AI", limit=5):
    url = f"https://rss.arxiv.org/rss/{category}"
    stories = []
    
    try:
        req = urllib.request.Request(
            url, 
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        )
        with urllib.request.urlopen(req, timeout=10) as response:
            xml_data = response.read()
            
        root = ET.fromstring(xml_data)
        items = root.findall(".//item")
        
        for item in items[:limit]:
            title = item.find("title").text if item.find("title") is not None else ""
            description = item.find("description").text if item.find("description") is not None else ""
            link = item.find("link").text if item.find("link") is not None else ""
            
            # Clean up arXiv title format (e.g., "Title (arXiv:2608.11207v1 [cs.AI])")
            clean_title = title.split("(")[0].strip() if title else "No Title"
            
            # Clean up abstract text
            content = description.strip().replace("\n", " ")
            
            stories.append({
                'title': clean_title,
                'content': content,
                'url': link.strip(),
                'source': f"arXiv ({category})"
            })
            
    except Exception as e:
        print(f"Warning: Failed to fetch arXiv RSS ({category}) - {e}")
        
    return stories

if __name__ == '__main__':
    import json
    results = fetch_arxiv(limit=10)
    print(json.dumps(results, ensure_ascii=False, indent=2))
