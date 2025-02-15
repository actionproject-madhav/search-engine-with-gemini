from flask import Flask, render_template, request
from urllib.parse import urlparse, urljoin
import sqlite3
import ssl
import socket

app = Flask(__name__)

# Gemini Fetching Functions
def fetch_gemini(url):
    try:
        parsed = urlparse(url)
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        context.minimum_version = ssl.TLSVersion.TLSv1_2
        context.set_ciphers('DEFAULT@SECLEVEL=1')

        with socket.create_connection((parsed.hostname, 1965), timeout=30) as sock:
            with context.wrap_socket(sock, server_hostname=parsed.hostname) as ssock:
                ssock.send(f"{url}\r\n".encode('utf-8'))
                response = b''
                while True:
                    data = ssock.recv(1024)
                    if not data:
                        break
                    response += data

        header, _, body = response.partition(b'\r\n')
        status = int(header.decode().split()[0])
        meta = ' '.join(header.decode().split()[1:])
        return status, meta, body.decode('utf-8', 'ignore')
        
    except Exception as e:
        print(f"Fetch error: {str(e)}")
        return None, None, None

def gemini_to_html(content, base_url):
    html_lines = []
    for line in content.split('\n'):
        if line.startswith('=>'):
            parts = line[2:].strip().split()
            if parts:
                link = parts[0]
                text = ' '.join(parts[1:]) if len(parts) > 1 else link
                absolute_url = urljoin(base_url, link)
                html_lines.append(f'<p><a href="/proxy?url={absolute_url}">{text}</a></p>')
        elif line.startswith('#'):
            level = min(line.count('#'), 3)
            text = line.lstrip('#').strip()
            html_lines.append(f'<h{level}>{text}</h{level}>')
        else:
            html_lines.append(f'<p>{line}</p>')
    return '\n'.join(html_lines)

# Search Functions
def search_database(query_terms):
    if not query_terms:
        return []
    
    try:
        conn = sqlite3.connect('index.db')
        query = " INTERSECT ".join(["SELECT url FROM index_table WHERE term = ?"] * len(query_terms))
        cursor = conn.execute(query, query_terms)
        results = [row[0] for row in cursor.fetchall()]
        conn.close()
        return results
    except Exception as e:
        print(f"Search error: {e}")
        return []

# Flask Routes
@app.route('/')
def index():
    return render_template('search.html')

@app.route('/search')
def handle_search():
    try:
        query = request.args.get('q', '').strip()
        if not query:
            return render_template('search.html', error="Please enter a search term.")

        terms = query.lower().split()
        urls = search_database(terms)
        results = []

        conn = sqlite3.connect('crawler.db')
        for url in urls[:20]:
            try:
                row = conn.execute("SELECT title, content FROM pages WHERE url = ?", (url,)).fetchone()
                if row:
                    title, content = row
                    snippet = ' '.join(content.split()[:30]) + '...'
                    results.append({
                        'url': url,
                        'title': title or url,
                        'snippet': snippet
                    })
            except Exception as e:
                print(f"Error processing {url}: {e}")
        conn.close()

        return render_template('results.html', query=query, results=results)

    except Exception as e:
        print(f"General error: {e}")
        return render_template('error.html', message="An error occurred during search")

@app.route('/proxy')
def handle_proxy():
    url = request.args.get('url')
    if not url or not url.startswith('gemini://'):
        return "Invalid URL", 400

    try:
        # Check cache first
        conn = sqlite3.connect('crawler.db')
        cached = conn.execute("SELECT content FROM pages WHERE url = ?", (url,)).fetchone()
        
        if cached:
            content = cached[0]
        else:
            status, meta, content = fetch_gemini(url)
            if status != 20:
                return f"Error fetching content (Status: {status})", 502

        html_content = gemini_to_html(content, url)
        return render_template('proxy.html', content=html_content, url=url)
        
    except Exception as e:
        print(f"Proxy error: {str(e)}")
        return "Error fetching content", 500
    finally:
        if 'conn' in locals():
            conn.close()

if __name__ == '__main__':
    app.run(debug=True)