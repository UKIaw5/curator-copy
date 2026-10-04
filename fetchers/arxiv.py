import re
import requests
import xml.etree.ElementTree as ET

ATOM_NS = {"atom": "http://www.w3.org/2005/Atom"}

def fetch_arxiv(category="cs.AI", limit=15):
    """arXivの検索APIから、投稿日の新しい順に論文を取得する。

    以前はRSSフィード(rss.arxiv.org)を使っていたが、あれは「その日に
    新規配信された分だけ」の日次フィードで、arXiv自体が土日に新規announceを
    行わないため土日は0件になる(バグではなく仕様)。検索APIは直近の投稿を
    日付でソートして返すので、土日でも直前の配信日(金曜等)まで遡って取得
    できる。重複排除は呼び出し側(output/history.json・seen_urls.json)で
    行われるため、ここでは単純に「直近のN件」を返せば十分。
    """
    url = "http://export.arxiv.org/api/query"
    params = {
        "search_query": f"cat:{category}",
        "sortBy": "submittedDate",
        "sortOrder": "descending",
        "start": 0,
        "max_results": limit,
    }
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    stories = []

    try:
        response = requests.get(url, params=params, headers=headers, timeout=15)
        response.raise_for_status()

        root = ET.fromstring(response.content)
        entries = root.findall("atom:entry", ATOM_NS)

        for entry in entries:
            title_el = entry.find("atom:title", ATOM_NS)
            summary_el = entry.find("atom:summary", ATOM_NS)
            id_el = entry.find("atom:id", ATOM_NS)
            link_el = entry.find("atom:link[@rel='alternate']", ATOM_NS)

            title = re.sub(r"\s+", " ", title_el.text).strip() if title_el is not None and title_el.text else "No Title"
            content = re.sub(r"\s+", " ", summary_el.text).strip() if summary_el is not None and summary_el.text else ""
            link = (link_el.attrib.get("href") if link_el is not None else None) or (id_el.text.strip() if id_el is not None and id_el.text else "")

            stories.append({
                'title': title,
                'content': content,
                'url': link,
                'source': f"arXiv ({category})"
            })

    except Exception as e:
        print(f"Warning: Failed to fetch arXiv ({category}) - {e}")

    return stories

if __name__ == '__main__':
    import json
    results = fetch_arxiv(limit=10)
    print(json.dumps(results, ensure_ascii=False, indent=2))
