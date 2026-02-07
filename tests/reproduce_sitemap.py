
import asyncio
import logging
import urllib.parse
from unittest.mock import MagicMock, AsyncMock
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading
import sys
import os

sys.path.append(os.getcwd())

from src.crawler_service import CrawlerService

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Mock Server
class MockHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/robots.txt':
            self.send_response(200)
            self.send_header('Content-type', 'text/plain')
            self.end_headers()
            self.wfile.write(b"Sitemap: http://localhost:8000/sitemap.xml")
        elif self.path == '/sitemap.xml':
            self.send_response(200)
            self.send_header('Content-type', 'application/xml')
            self.end_headers()
            content = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
   <url>
      <loc>http://localhost:8000/page1</loc>
   </url>
   <url>
      <loc>http://localhost:8000/level1/page2</loc>
   </url>
</urlset>"""
            self.wfile.write(content.encode('utf-8'))
        elif self.path in ['/page1', '/level1/page2']:
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            self.wfile.write(f"<html><body><h1>This is {self.path}</h1></body></html>".encode('utf-8'))
        else:
            self.send_response(404)
            self.end_headers()

def start_server():
    server = HTTPServer(('localhost', 8000), MockHandler)
    server_thread = threading.Thread(target=server.serve_forever)
    server_thread.daemon = True
    server_thread.start()
    return server

async def test_crawler_sitemap():
    # Mock dependencies
    mock_db = AsyncMock()
    mock_db.scraping = AsyncMock()
    mock_db.scraping.create.return_value = MagicMock(id="mock_id")
    mock_db.scraping.update = AsyncMock()
    
    # We need a base_url record
    mock_base_url_record = MagicMock()
    mock_base_url_record.BaseUrl = "http://localhost:8000"
    mock_base_url_record.id = "base_id"
    mock_base_url_record.strictCheck = False
    
    mock_s3 = MagicMock()
    mock_s3.upload_html.return_value = "s3_key"
    
    # Initialize Crawler
    crawler = CrawlerService(mock_db, mock_s3)
    
    print("Starting crawl...")
    try:
        await crawler.crawl(mock_base_url_record)
    except Exception as e:
        logger.error(f"Crawl failed: {e}")

    # Verification
    # Check calls to scraping.create to see depth
    # We expect:
    # /page1 -> depth 1
    # /level1/page2 -> depth 2
    
    calls = mock_db.scraping.create.call_args_list
    for call in calls:
        args, kwargs = call
        data = kwargs.get('data', {})
        url = data.get('url')
        depth = data.get('depth')
        print(f"URL: {url}, Depth: {depth}")

    print("Test finished.")

if __name__ == "__main__":
    start_server()
    asyncio.run(test_crawler_sitemap())
