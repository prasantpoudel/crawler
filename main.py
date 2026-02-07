import asyncio
import logging
from dotenv import load_dotenv
from datetime import datetime

from prisma import Prisma
from src.crawler_service import CrawlerService
from src.s3_uploader import S3Uploader

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    filename=f"logs/{datetime.now().strftime('%Y-%m-%d_%H-%M')}.txt",
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def main():
    load_dotenv(override=True)
    
    db = Prisma()
    await db.connect()
    
    s3_uploader = S3Uploader()
    crawler = CrawlerService(db, s3_uploader)
    
    try:
        urls_to_crawl = await db.urls.find_many(where={'inPipeline':True})
        
        if not urls_to_crawl:
            logger.info("No URLs found in the database to crawl.")
            return

        for url_record in urls_to_crawl:
             logger.info(f"Starting crawl for base URL: {url_record.BaseUrl}")
             await crawler.crawl(url_record)
             
    except Exception as e:
        logger.error(f"An error occurred during execution: {e}")
    finally:
        if db.is_connected():
            await db.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
