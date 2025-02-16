import sqlite3
import ssl
import socket
from urllib.parse import urlparse, urljoin
from queue import Queue
import time
import random
import logging

class GeminiCrawler:
    def __init__(self, db_name='crawler.db'):
        self.queue = Queue()
        # Expanded seed list with popular Gemini portals
        self.seeds = [
    'gemini://gemini.circumlunar.space',      
    'gemini://geminispace.info',              
    'gemini://mozz.us/',                      
    'gemini://rawtext.club/',                 
    'gemini://kennedy.gemi.dev/',             
    'gemini://gemi.dev/',                    
    'gemini://gemini.bortzmeyer.org/',        
    'gemini://gemini.philipp.codes/',        
    'gemini://gemi.space/',                   
    'gemini://gemini.papillon.art/',         
    'gemini://alexandria.legion.am/',         
    'gemini://furryfandom.gemini/',          
    'gemini://gemin.space/',                  
    'gemini://finzi.tech/',                   
    'gemini://gemini.hitchhiker.net/',        
    'gemini://gnotty.nikiv.dev/',             
    'gemini://solar.systems/',                
    'gemini://wq1.runkarv.moe/',              
    'gemini://docs.gemini/',                  
    'gemini://distributopia.space/',          
    'gemini://lunar.cat/',                    
    'gemini://tildes.net/',                   
    'gemini://yourpersonalblog.gemini/',      
    'gemini://tilde.town/',                   
    'gemini://thejefffiles.com/',             
    'gemini://gemi.space/',                   
    'gemini://sdf.org/',                      
    'gemini://sunflower.gemini/',             
    'gemini://thetotality.gemini/',           
    'gemini://neocities.space/',              
    'gemini://src.gitlab.com/',               
]

        for url in self.seeds:
            self.queue.put(url)
        self.visited = set()
        self.db_conn = sqlite3.connect(db_name)
        self.cursor = self.db_conn.cursor()
        self._init_db()
        logging.basicConfig(level=logging.INFO)
        print("Database initialized")

    def _init_db(self):
        self.cursor.execute('''CREATE TABLE IF NOT EXISTS pages
                            (url TEXT PRIMARY KEY, 
                             title TEXT,
                             content TEXT,
                             fetched_at TIMESTAMP)''')
        self.cursor.execute('''CREATE INDEX IF NOT EXISTS idx_fetched 
                            ON pages(fetched_at)''')
        self.db_conn.commit()

    def fetch_gemini(self, url):
        try:
            parsed = urlparse(url)
            logging.info(f"Connecting to {parsed.hostname}...")
            
            # Configure modern TLS with fallback
            context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE
            context.minimum_version = ssl.TLSVersion.TLSv1_2
            context.set_ciphers('DEFAULT:@SECLEVEL=1')

            with socket.create_connection((parsed.hostname, 1965), timeout=30) as sock:
                with context.wrap_socket(sock, server_hostname=parsed.hostname) as ssock:
                    ssock.send(f"{url}\r\n".encode('utf-8'))
                    response = self._receive_full_response(ssock)
                    
            header, _, body = response.partition(b'\r\n')
            return self._process_response(header, body, url)
            
        except Exception as e:
            logging.error(f"Error fetching {url}: {str(e)}")
            return None, None, None

    def _receive_full_response(self, sock, chunk_size=4096):
        response = b''
        while True:
            try:
                data = sock.recv(chunk_size)
                if not data:
                    break
                response += data
            except socket.timeout:
                break
        return response

    def _process_response(self, header, body, url):
        try:
            status = int(header.decode().split()[0])
            meta = ' '.join(header.decode().split()[1:])
            content = body.decode('utf-8', 'ignore')
            return status, meta, content
        except Exception as e:
            logging.error(f"Error processing response from {url}: {str(e)}")
            return None, None, None

    def extract_links(self, base_url, content):
        links = []
        for line in content.split('\n'):
            if line.startswith('=>'):
                parts = line[2:].strip().split()
                if parts:
                    raw_link = parts[0]
                    absolute_url = urljoin(base_url, raw_link)
                    if absolute_url.startswith('gemini://'):
                        normalized = self._normalize_url(absolute_url)
                        links.append(normalized)
        logging.info(f"Found {len(links)} links")
        return links

    def _normalize_url(self, url):
        parsed = urlparse(url)
        path = parsed.path.rstrip('/') if parsed.path != '/' else '/'
        return f"{parsed.scheme}://{parsed.netloc}{path}"

    def run(self, max_pages=100000):
        try:
            while len(self.visited) < max_pages and not self.queue.empty():
                url = self.queue.get()
                if url in self.visited:
                    continue
                
                logging.info(f"\n=== Crawling {url} ===")
                status, meta, content = self.fetch_gemini(url)
                
                if status in (30, 31):
                    self._handle_redirect(url, meta)
                elif status == 20:
                    self._store_page(url, content)
                    self._enqueue_links(url, content)
                else:
                    logging.warning(f"Skipping URL (Status: {status}, Meta: {meta})")

                self.visited.add(url)
                self._adaptive_sleep(len(self.visited))
                
        finally:
            self.db_conn.close()
            logging.info("\nCrawling session ended")
            logging.info(f"Total pages crawled: {len(self.visited)}")
            logging.info(f"Queue size remaining: {self.queue.qsize()}")

    def _handle_redirect(self, url, meta):
        new_url = urljoin(url, meta)
        normalized = self._normalize_url(new_url)
        if normalized not in self.visited and normalized not in list(self.queue.queue):
            logging.info(f"Redirect to: {normalized}")
            self.queue.put(normalized)

    def _store_page(self, url, content):
        title = self.extract_title(content)
        try:
            self.cursor.execute('''INSERT OR REPLACE INTO pages 
                                  VALUES (?, ?, ?, ?)''',
                                (url, title, content, time.time()))
            self.db_conn.commit()
            logging.info(f"Saved: {url}")
        except Exception as e:
            logging.error(f"Database error: {str(e)}")
            self.db_conn.rollback()

    def _enqueue_links(self, url, content):
        links = self.extract_links(url, content)
        for link in links:
            if link not in self.visited and link not in list(self.queue.queue):
                self.queue.put(link)
                logging.debug(f"Queued: {link}")

    def extract_title(self, content):
        for line in content.split('\n'):
            line = line.strip()
            if line.startswith('# ') and len(line) > 2:
                return line[2:].strip()[:200]
        return "Untitled Document"

    def _adaptive_sleep(self, crawled_count):
        base_delay = 0.1  # Reduce base delay
        jitter = random.uniform(0.5, 1.0)  # Less variation
        time.sleep(base_delay * jitter)

if __name__ == '__main__':
    crawler = GeminiCrawler()
    crawler.run(max_pages=100000)  # Now set to crawl 1000 pages