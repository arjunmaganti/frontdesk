#!/usr/bin/env python3
import os
import sys
import shutil
import unittest

# Ensure the parent directory is in the path so we can import utility modules
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from utility.crawl import crawl_site

class TestCrawler(unittest.TestCase):
    def setUp(self):
        self.test_out_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "test_crawl_output"))
        if os.path.exists(self.test_out_dir):
            shutil.rmtree(self.test_out_dir)

    def tearDown(self):
        if os.path.exists(self.test_out_dir):
            shutil.rmtree(self.test_out_dir)

    def test_crawl_green_foliage(self):
        target_url = "https://greenfoliageunlimitedinc.com/"
        print(f"\n[Test] Crawling {target_url}...")
        
        # Crawl only 1 page to verify core functionality
        crawl_site(target_url, self.test_out_dir, max_pages=1, max_depth=0)
        
        # Verify the output directory exists
        self.assertTrue(os.path.exists(self.test_out_dir), "Output directory was not created.")
        
        # Verify index.md was created
        index_file = os.path.join(self.test_out_dir, "index.md")
        self.assertTrue(os.path.exists(index_file), "index.md was not generated.")
        
        # Read file contents
        with open(index_file, "r", encoding="utf-8") as f:
            content = f.read().strip()
            
        # Verify file is not empty
        self.assertTrue(len(content) > 0, "Generated index.md is empty.")
        
        # Verify specific content fragments exist
        self.assertIn("Green Foliage", content, "Expected text 'Green Foliage' not found in index.md.")
        self.assertIn("Landscaping", content, "Expected text 'Landscaping' not found in index.md.")
        
        print("✅ Crawler test successful! Generated file has content and correct keywords.")

if __name__ == "__main__":
    unittest.main()
