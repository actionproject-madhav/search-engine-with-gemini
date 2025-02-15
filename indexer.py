import sqlite3
import re
import string

class Indexer:
    def __init__(self, crawler_db='crawler.db', index_db='index.db'):
        self.crawler_conn = sqlite3.connect(crawler_db)
        self.index_conn = sqlite3.connect(index_db)
        self.cursor = self.index_conn.cursor()
        self.cursor.execute('''CREATE TABLE IF NOT EXISTS index_table
                            (term TEXT, url TEXT, PRIMARY KEY (term, url))''')

    def tokenize(self, text):
        text = text.lower()
        text = text.translate(str.maketrans('', '', string.punctuation))
        words = re.findall(r'\b\w+\b', text)
        return words

    def process_page(self, content):
        return ' '.join(content.split())

    def build_index(self):
        cur = self.crawler_conn.cursor()
        cur.execute("SELECT url, content FROM pages")
        for url, content in cur:
            text = self.process_page(content)
            words = self.tokenize(text)
            for word in words:
                self.cursor.execute("INSERT OR IGNORE INTO index_table VALUES (?, ?)", (word, url))
        self.index_conn.commit()
        self.crawler_conn.close()
        self.index_conn.close()

if __name__ == '__main__':
    indexer = Indexer()
    indexer.build_index()