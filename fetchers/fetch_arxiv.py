import requests
import xml.etree.ElementTree as ET
from typing import List, Dict

def fetch_arxiv_papers(query="cat:cs.CL AND (LLM OR \"Language Model\")", max_results=5) -> List[Dict[str, str]]:
    url = f"http://export.arxiv.org/api/query?search_query={query}&sortBy=submittedDate&sortOrder=desc&max_results={max_results}"
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) SourceCuratorBot/1.0'}
    
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        
        root = ET.fromstring(response.content)
        entries = root.findall(".//{http://www.w3.org/2005/Atom}entry")
        
        papers = []
        for entry in entries:
            title = entry.find("{http://www.w3.org/2005/Atom}title").text.strip()
            summary = entry.find("{http://www.w3.org/2005/Atom}summary").text.strip()
            
            # Extract URL from <id> or <link rel="alternate">
            url = entry.find("{http://www.w3.org/2005/Atom}id").text
            link = entry.find(".//{http://www.w3.org/2005/Atom}link[@rel='alternate']")
            if link is not None:
                url = link.attrib.get('href')
            
            papers.append({
                "title": title,
                "content": summary,
                "url": url,
                "source": "ArXiv"
            })
        
        return papers
    
    except requests.RequestException as e:
        print(f"HTTP request error: {e}")
    except ET.ParseError as e:
        print(f"XML parsing error: {e}")
    
    return []

if __name__ == '__main__':
    results = fetch_arxiv_papers()
    import json
    print(json.dumps(results, ensure_ascii=False, indent=2))