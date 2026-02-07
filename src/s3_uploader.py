import boto3
import os
import gzip
from botocore.exceptions import NoCredentialsError
import logging

logger = logging.getLogger(__name__)

class S3Uploader:
    def __init__(self):
        self.bucket_name = os.getenv("S3_BUCKET_NAME")
        self.bucker_prefix = os.getenv("S3_BUCKET_PREFIX")
        self.s3 = boto3.client('s3')

    def upload_html(self, content: str, base_url_id: str, version: str, url_encoded: str) -> str:
        """
        Uploads HTML content to S3.
        Returns the S3 key.
        """
        if not self.bucket_name:
            logger.error("S3_BUCKET_NAME is not set in environment variables.")
            return None

        # Compress content
        compressed_content = gzip.compress(content.encode('utf-8'))

        # Construct S3 key: {base_url_id}/{version}/{url_encoded}.html
        key = f"{self.bucker_prefix}/{base_url_id}/{version}/{url_encoded}.html"

        try:
            self.s3.put_object(
                Bucket=self.bucket_name,
                Key=key,
                Body=compressed_content,
                ContentType='text/html',
                ContentEncoding='gzip'
            )
            logger.info(f"Successfully uploaded {key} to S3.")
            return key
        except NoCredentialsError:
            logger.error("AWS credentials not available.")
            return None
        except Exception as e:
            logger.error(f"Failed to upload to S3: {e}")
            return None
