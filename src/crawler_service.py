import asyncio
import logging
import urllib.parse
import hashlib
from typing import Set, Optional
import os

from prisma import Prisma
from prisma.models import Urls
from prisma.enums import Status

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from bs4 import BeautifulSoup
import urllib.robotparser
import urllib.request
import xml.etree.ElementTree as ET

from src.s3_uploader import S3Uploader

logger = logging.getLogger(__name__)

class CrawlerService:
    def __init__(self, db: Prisma, s3_uploader: S3Uploader):
        self.db = db
        self.s3_uploader = s3_uploader
        self.driver = None
        self.visited_urls: Set[str] = set()
        self.base_url_id: Optional[str] = None
        self.base_url: Optional[str] = None
        self.version: str = os.getenv("VERSION")
        self.rp = urllib.robotparser.RobotFileParser()

    def setup_driver(self):
        chrome_options = Options()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        
        self.driver = webdriver.Chrome(
            options=chrome_options
        )

    def close_driver(self):
        if self.driver:
            self.driver.quit()

    async def _ensure_robots_txt(self):
        if self.rp.mtime() == 0:
            parsed_base = urllib.parse.urlparse(self.base_url)
            robots_url = f"{parsed_base.scheme}://{parsed_base.netloc}/robots.txt"
            logger.info(f"Checking robots.txt at {robots_url}")
            try:
                self.rp.set_url(robots_url)
                loop = asyncio.get_running_loop()
                await loop.run_in_executor(None, self.rp.read)
            except Exception as e:
                logger.warning(f"Could not read robots.txt: {e}")

    async def can_fetch(self, url: str) -> bool:
        if not self.base_url:
            return False
            
        await self._ensure_robots_txt()
        return self.rp.can_fetch("*", url)

    async def fetch_sitemap_content(self, url: str) -> Optional[bytes]:
        try:
            loop = asyncio.get_running_loop()
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            return await loop.run_in_executor(None, lambda: urllib.request.urlopen(req).read())
        except Exception as e:
            logger.warning(f"Failed to fetch sitemap {url}: {e}")
            return None

    async def parse_sitemap(self, url: str) -> Set[str]:
        content = await self.fetch_sitemap_content(url)
        if not content:
            return set()
            
        urls = set()
        try:
            root = ET.fromstring(content)
            # Handle namespace
            namespaces = {'ns': 'http://www.sitemaps.org/schemas/sitemap/0.9'}
            
            # Check for sitemapindex
            for sitemap in root.findall('ns:sitemap', namespaces):
                loc = sitemap.find('ns:loc', namespaces)
                if loc is not None and loc.text:
                    urls.update(await self.parse_sitemap(loc.text))
            
            # Check for url entries
            for url_tag in root.findall('ns:url', namespaces):
                loc = url_tag.find('ns:loc', namespaces)
                if loc is not None and loc.text:
                    urls.add(loc.text)
                    
        except ET.ParseError as e:
            logger.warning(f"Failed to parse sitemap {url}: {e}")
            
        return urls
    
    def _calculate_depth(self, url: str) -> int:
        try:
            base_parsed = urllib.parse.urlparse(self.base_url)
            url_parsed = urllib.parse.urlparse(url)
            
            # Remove leading/trailing slashes and split
            base_path = [p for p in base_parsed.path.strip('/').split('/') if p]
            url_path = [p for p in url_parsed.path.strip('/').split('/') if p]
            
            depth = len(url_path) - len(base_path)
            return max(0, depth)
        except Exception:
            return 1

    async def get_sitemap_urls(self) -> Set[str]:
        sitemap_urls = set()
        
        await self._ensure_robots_txt()
        
        # Check robots.txt for sitemaps
        # site_maps() can return None if not found or not initialized
        robots_sitemaps = self.rp.site_maps() or []
        
        if robots_sitemaps:
            for sm_url in robots_sitemaps:
                sitemap_urls.update(await self.parse_sitemap(sm_url))
        
        # Check standard sitemap location if none found in robots.txt
        # Or should we check it anyway? Standard practice is often to check both.
        # But let's avoid duplicates if robots.txt already pointed to it.
        parsed_base = urllib.parse.urlparse(self.base_url)
        standard_sitemap = f"{parsed_base.scheme}://{parsed_base.netloc}/sitemap.xml"
        if standard_sitemap not in robots_sitemaps and not sitemap_urls:
             sitemap_urls.update(await self.parse_sitemap(standard_sitemap))

        return sitemap_urls

    async def crawl(self, base_url_record: Urls):
        self.base_url_record = base_url_record
        self.base_url = base_url_record.BaseUrl
        self.base_url_id = base_url_record.id
        
        logger.info(f"Starting crawl for {self.base_url}")
        
        self.setup_driver()
        
        try:
            sitemap_urls = await self.get_sitemap_urls()
            
            if sitemap_urls:
                logger.info(f"Found {len(sitemap_urls)} URLs in sitemap. Crawling them directly.")
                for url in sitemap_urls:
                    if await self.can_fetch(url):
                         # If strict check is on, ensure it matches base domain
                         if self.base_url_record.strictCheck:
                             if not url.startswith(self.base_url):
                                 continue
                         depth = self._calculate_depth(url)
                         await self.process_url(url, depth=depth, extract_links=False)
            else:
                logger.info("No sitemap found. Falling back to recursive crawling.")
                await self.process_url(self.base_url, depth=0, extract_links=True)
        finally:
            self.close_driver()

    async def process_url(self, url: str, depth: int, max_depth: int = 3, extract_links: bool = True):
        if extract_links and depth > max_depth:
            return
        
        if url in self.visited_urls:
            return
        self.visited_urls.add(url)

        # Check robots.txt
        if not await self.can_fetch(url):
            logger.info(f"Skipping {url} due to robots.txt")
            return

        logger.info(f"Processing {url} at depth {depth}")

        # Create initial scraping record
        scraping_record = await self.db.scraping.create(
            data={
                "baseUrlId": self.base_url_id,
                "url": url,
                "status": Status.IN_PROGESS,
                "depth": depth
            }
        )

        try:
            self.driver.get(url)
            # Add some wait time or smart waiting here if needed
            await asyncio.sleep(3) 
            
            page_content = self.driver.page_source
            soup = BeautifulSoup(page_content, 'html.parser')
            
            # Save to S3
            url_encoded = urllib.parse.quote(url, safe='')
            page_hash = hashlib.md5(page_content.encode('utf-8')).hexdigest()
            
            s3_key = self.s3_uploader.upload_html(
                content=page_content,
                base_url_id=self.base_url_id,
                version=self.version,
                url_encoded=url_encoded
            )

            # Update scraping record
            await self.db.scraping.update(
                where={"id": scraping_record.id},
                data={
                    "status": Status.SUCESS,
                    "pageHash": page_hash,
                    "s3Key": s3_key
                }
            )

            # Find child links using BS4
            if extract_links and depth < max_depth:
                links = soup.find_all('a', href=True)
                for link in links:
                    next_url = urllib.parse.urljoin(url, link['href'])
                    
                    # Validation Logic
                    should_scrape = False
                    if self.base_url_record.strictCheck:
                        # strict_check: new url must start with base_url
                        if next_url.startswith(self.base_url):
                            should_scrape = True
                    else:
                        # standard check: same domain
                        if urllib.parse.urlparse(next_url).netloc == urllib.parse.urlparse(self.base_url).netloc:
                            should_scrape = True
                    
                    if should_scrape:
                        await self.process_url(next_url, depth + 1, max_depth, extract_links=True)

        except Exception as e:
            logger.error(f"Error processing {url}: {e}")
            await self.db.scraping.update(
                where={"id": scraping_record.id},
                data={
                    "status": Status.FAILED,
                    "error": str(e)
                }
            )

