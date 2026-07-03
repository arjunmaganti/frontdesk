#!/usr/bin/env python3
import os
import sys
import argparse
import re
import asyncio
from urllib.parse import urlparse

try:
    import crawl4ai
    from crawl4ai import AsyncWebCrawler
except ImportError:
    print("Error: Required crawl4ai library not installed. Please run: pip install requirements.txt")
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

async def crawl_site_async(start_url, out_dir, max_pages, max_depth):
    """Asynchronously crawls the website using Crawl4AI."""
    os.makedirs(out_dir, exist_ok=True)
    
    parsed_start = urlparse(start_url)
    domain = parsed_start.netloc
    
    visited = set()
    queue = [(start_url, 0)]  # Queue contains tuples of (url, depth)
    pages_crawled = 0
    
    print(f"🕸️ Starting crawl of '{start_url}' using Crawl4AI (Domain: {domain})")
    print(f"Configuration: Max Pages: {max_pages} | Max Depth: {max_depth} | Output Dir: {out_dir}\n")

    async with AsyncWebCrawler() as crawler:
        while queue and pages_crawled < max_pages:
            url, depth = queue.pop(0)
            
            if url in visited or depth > max_depth:
                continue
                
            visited.add(url)
            print(f"[{pages_crawled + 1}] Crawling: {url} (Depth: {depth})")
            
            try:
                # Crawl4AI renders Javascript natively via Playwright
                result = await crawler.arun(url=url)
                if not result.success:
                    print(f"⚠️ Failed to fetch {url}")
                    continue
                
                # Retrieve fully rendered markdown content
                markdown_content = result.markdown
                if not markdown_content:
                    print(f"⚠️ Warning: Crawl succeeded but extracted markdown is empty for {url}")
                    continue
                
                # Generate index file name and path
                filename = clean_filename(url, domain)
                filepath = os.path.join(out_dir, filename)
                
                # Prepend source URL metadata to document
                formatted_markdown = f"# Source: {url}\n\n{markdown_content}"
                
                with open(filepath, "w", encoding="utf-8") as f:
                    f.write(formatted_markdown)
                print(f"💾 Saved as: {filepath}")
                
                pages_crawled += 1
                
                # Check for child links if within allowed depth
                if depth < max_depth and result.links:
                    internal_links = result.links.get("internal", [])
                    for link_info in internal_links:
                        link_url = link_info.get("href")
                        if not link_url:
                            continue
                            
                        # Strip hash fragments from target link
                        link_url = link_url.split("#")[0]
                        parsed_link = urlparse(link_url)
                        
                        # Only follow links belonging to the same host domain
                        if parsed_link.netloc == domain and link_url not in visited:
                            queue.append((link_url, depth + 1))
                            
            except Exception as e:
                print(f"⚠️ Error crawling {url}: {e}")

def crawl_site(start_url, out_dir, max_pages, max_depth):
    """Synchronous entry wrapper for crawl_site_async."""
    asyncio.run(crawl_site_async(start_url, out_dir, max_pages, max_depth))

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Business Website Policy Crawler (Crawl4AI Version)")
    parser.add_argument("--url", required=True, help="Homepage URL to start crawling from")
    parser.add_argument("--out", required=True, help="Directory to save output Markdown files (e.g. data/)")
    parser.add_argument("--max-pages", type=int, default=15, help="Maximum number of pages to crawl (default 15)")
    parser.add_argument("--depth", type=int, default=2, help="Maximum crawling depth (default 2)")
    
    args = parser.parse_args()
    
    # Prepend schema if missing
    target_url = args.url
    if not target_url.startswith("http://") and not target_url.startswith("https://"):
        target_url = "https://" + target_url
        
    crawl_site(target_url, args.out, args.max_pages, args.depth)
