import urllib.parse

class MockCrawler:
    def __init__(self, base_url):
        self.base_url = base_url
    
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

# Test cases
crawler = MockCrawler("http://example.com")
print(f"Base: {crawler.base_url}")
print(f"http://example.com -> {crawler._calculate_depth('http://example.com')}")
print(f"http://example.com/ -> {crawler._calculate_depth('http://example.com/')}")
print(f"http://example.com/a -> {crawler._calculate_depth('http://example.com/a')}")
print(f"http://example.com/a/b -> {crawler._calculate_depth('http://example.com/a/b')}")

crawler2 = MockCrawler("http://example.com/blog")
print(f"Base: {crawler2.base_url}")
print(f"http://example.com/blog -> {crawler2._calculate_depth('http://example.com/blog')}")
print(f"http://example.com/blog/2023 -> {crawler2._calculate_depth('http://example.com/blog/2023')}")
