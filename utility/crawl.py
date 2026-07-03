import os
import sys
import argparse
import re
from urllib.parse import urlparse, urljoin

try:
    import requests
    from bs4 import BeautifulSoup
except ImportError:
    print("Error: Required libraries not installed. Please run: pip install requirements.txt")
    sys.exit(1)

def clean_filename(url, domain):
    """Generates a clean, readable .md filename from a URL."""
    path = urlparse(url).path
    if not path or path == "/":
        return "index.md"
    
    # Remove trailing slashes and clean characters
    path = path.strip("/")
    clean_name = re.sub(r"[^a-zA-Z0-9_\-]", "_", path)
    return f"{clean_name}.md"

def html_to_markdown(html_content, page_url):
    """Parses HTML, removes menus/headers/footers, and converts body elements to clean Markdown."""
    soup = BeautifulSoup(html_content, "html.parser")
    
    # 1. Strip non-content elements to avoid RAG noise
    for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
        tag.decompose()
        
    # Attempt to locate the main content area first, fallback to body
    content_area = soup.find("main") or soup.find("article") or soup.find("body")
    if not content_area:
        return ""
        
    markdown_lines = []
    
    # Extract page title
    title = soup.title.string if soup.title else ""
    if title:
        markdown_lines.append(f"# {title.strip()}\n")
        markdown_lines.append(f"Source URL: {page_url}\n\n---\n")

    # Traverse elements and format to markdown
    for element in content_area.find_all(["h1", "h2", "h3", "h4", "p", "li"]):
        text = element.get_text().strip()
        if not text:
            continue
            
        tag_name = element.name
        if tag_name == "h1":
            markdown_lines.append(f"\n# {text}\n")
        elif tag_name == "h2":
            markdown_lines.append(f"\n## {text}\n")
        elif tag_name == "h3":
            markdown_lines.append(f"\n### {text}\n")
        elif tag_name == "h4":
            markdown_lines.append(f"\n#### {text}\n")
        elif tag_name == "p":
            markdown_lines.append(f"\n{text}\n")
        elif tag_name == "li":
            # Check if parent is an ordered list
            is_ordered = element.parent and element.parent.name == "ol"
            bullet = "1." if is_ordered else "*"
            markdown_lines.append(f"{bullet} {text}")
            
    return "\n".join(markdown_lines)

def crawl_site(start_url, out_dir, max_pages, max_depth):
    os.makedirs(out_dir, exist_ok=True)
    
    parsed_start = urlparse(start_url)
    domain = parsed_start.netloc
    
    visited = set()
    queue = [(start_url, 0)]  # Tuple: (url, depth)
    pages_crawled = 0
    
    print(f"🕸️ Starting crawl of '{start_url}' (Domain: {domain})")
    print(f"Configuration: Max Pages: {max_pages} | Max Depth: {max_depth} | Output Dir: {out_dir}\n")

    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    while queue and pages_crawled < max_pages:
        url, depth = queue.pop(0)
        
        if url in visited or depth > max_depth:
            continue
            
        visited.add(url)
        print(f"[{pages_crawled + 1}] Crawling: {url} (Depth: {depth})")
        
        try:
            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code != 200:
                print(f"⚠️ Failed to fetch {url} (Status: {response.status_code})")
                continue
                
            content_type = response.headers.get("Content-Type", "")
            if "text/html" not in content_type:
                print(f"⚠️ Skipping non-HTML page: {url} ({content_type})")
                continue
                
            # 1. Convert HTML content to Markdown
            markdown = html_to_markdown(response.text, url)
            
            # 2. Save file
            filename = clean_filename(url, domain)
            filepath = os.path.join(out_dir, filename)
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(markdown)
            print(f"💾 Saved as: {filepath}")
            
            pages_crawled += 1
            
            # 3. Find links on the page for further crawling
            if depth < max_depth:
                soup = BeautifulSoup(response.text, "html.parser")
                for link in soup.find_all("a", href=True):
                    href = link["href"]
                    # Resolve relative links
                    absolute_url = urljoin(url, href)
                    
                    # Normalize URL (strip fragment anchor)
                    absolute_url = absolute_url.split("#")[0]
                    
                    # Ensure the link belongs to the same domain and hasn't been visited
                    parsed_link = urlparse(absolute_url)
                    if parsed_link.netloc == domain and absolute_url not in visited:
                        queue.append((absolute_url, depth + 1))
                        
        except Exception as e:
            print(f"⚠️ Error crawling {url}: {e}")
            
    print(f"\nCrawl complete. Successfully generated {pages_crawled} Markdown file(s) in: {out_dir}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Business Website Policy Crawler")
    parser.add_argument("--url", required=True, help="Homepage URL to start crawling from")
    parser.add_argument("--out", required=True, help="Directory to save output Markdown files (e.g. data/)")
    parser.add_argument("--max-pages", type=int, default=15, help="Maximum number of pages to crawl (default 15)")
    parser.add_argument("--depth", type=int, default=2, help="Maximum crawling depth (default 2)")
    
    args = parser.parse_args()
    
    # Simple validation for URL scheme
    target_url = args.url
    if not target_url.startswith("http://") and not target_url.startswith("https://"):
        target_url = "https://" + target_url
        
    crawl_site(target_url, args.out, args.max_pages, args.depth)
