import sqlite3
import ssl
import socket
from urllib.parse import urlparse, urljoin
from queue import Queue
import time
import random

class GeminiCrawler:
    def __init__(self, db_name='crawler.db'):
        self.queue = Queue()
        self.seeds = ['gemini://gemini.circumlunar.space']
        for url in self.seeds:
            self.queue.put(url)
        self.visited = set()
        self.db_conn = sqlite3.connect(db_name)
        self.cursor = self.db_conn.cursor()
        self.cursor.execute('''CREATE TABLE IF NOT EXISTS pages
                            (url TEXT PRIMARY KEY, 
                             title TEXT,
                             content TEXT,
                             fetched_at TIMESTAMP)''')
        self.db_conn.commit()
        print("Database initialized")

    def fetch_gemini(self, url):
        try:
            parsed = urlparse(url)
            print(f"Connecting to {parsed.hostname}...")
            
            # Modern TLS configuration
            context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE
            context.minimum_version = ssl.TLSVersion.TLSv1_2
            context.set_ciphers('DEFAULT@SECLEVEL=1')

            with socket.create_connection((parsed.hostname, 1965), timeout=30) as sock:
                print(f"Connected to {parsed.hostname}:1965")
                with context.wrap_socket(sock, server_hostname=parsed.hostname) as ssock:
                    print(f"SSL established. Requesting: {url}")
                    ssock.send(f"{url}\r\n".encode('utf-8'))
                    response = b''
                    while True:
                        data = ssock.recv(1024)
                        if not data:
                            break
                        response += data
                    print(f"Received {len(response)} bytes")

            header, _, body = response.partition(b'\r\n')
            status = int(header.decode().split()[0])
            meta = ' '.join(header.decode().split()[1:])
            return status, meta, body.decode('utf-8', 'ignore')
            
        except Exception as e:
            print(f"Error fetching {url}: {str(e)}")
            return None, None, None

    def extract_title(self, content):
        for line in content.split('\n'):
            if line.startswith('#') and not line.startswith('##'):
                return line.lstrip('#').strip()[:200]
        return "Untitled Document"

    def extract_links(self, base_url, content):
        links = []
        for line in content.split('\n'):
            if line.startswith('=>'):
                parts = line[2:].strip().split()
                if parts:
                    raw_link = parts[0]
                    absolute_url = urljoin(base_url, raw_link)
                    if absolute_url.startswith('gemini://'):
                        links.append(absolute_url)
        print(f"Found {len(links)} links")
        return links

    def run(self, max_pages=50):
        try:
            while not self.queue.empty() and len(self.visited) < max_pages:
                url = self.queue.get()
                if url in self.visited:
                    continue
                    
                print(f"\n=== Crawling {url} ===")
                status, meta, content = self.fetch_gemini(url)
                
                print(f"Status: {status}, Meta: {meta}")
                
                if status in (30, 31):  # Handle redirects
                    new_url = urljoin(url, meta)
                    print(f"Redirect ({status}) to: {new_url}")
                    if new_url not in self.visited and new_url not in list(self.queue.queue):
                        self.queue.put(new_url)
                elif status == 20:
                    print(f"Status 20 OK - Content type: {meta}")
                    title = self.extract_title(content)
                    print(f"Title extracted: {title}")
                    
                    try:
                        self.cursor.execute('''INSERT OR REPLACE INTO pages 
                                            VALUES (?, ?, ?, ?)''',
                                          (url, title, content, time.time()))
                        self.db_conn.commit()
                        print(f"Successfully saved to database: {url}")
                        
                        links = self.extract_links(url, content)
                        for link in links:
                            if link not in self.visited and link not in list(self.queue.queue):
                                self.queue.put(link)
                                print(f"Queued new URL: {link}")
                    except Exception as e:
                        print(f"Database error: {str(e)}")
                        self.db_conn.rollback()
                else:
                    print(f"Skipping URL (Status: {status}, Meta: {meta})")

                self.visited.add(url)
                time.sleep(random.uniform(1, 3))
                
        finally:
            self.db_conn.close()
            print("\nCrawling session ended")
            print(f"Total pages crawled: {len(self.visited)}")
            print(f"Queue size remaining: {self.queue.qsize()}")

if __name__ == '__main__':
    crawler = GeminiCrawler()
    crawler.run(max_pages=50)