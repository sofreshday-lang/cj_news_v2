from http.server import BaseHTTPRequestHandler
import json
import os
import urllib.request
import urllib.parse
from datetime import datetime, timedelta
import re
from difflib import SequenceMatcher

def clean_html(raw_html):
    if not raw_html: return ""
    cleanr = re.compile('<.*?>')
    cleantext = re.sub(cleanr, '', raw_html)
    cleantext = cleantext.replace('&quot;', '"').replace('&apos;', "'").replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>').replace('&middot;', '·')
    return cleantext

def parse_pubdate(pubdate_str):
    try:
        return datetime.strptime(pubdate_str, "%a, %d %b %Y %H:%M:%S %z")
    except:
        return None

def is_similar(a, b, threshold=0.8):
    if not a or not b: return False
    return SequenceMatcher(None, a, b).ratio() >= threshold

def process_news_search(client_id, client_secret, params):
    keywords = params.get('keywords', [])
    custom_keyword = params.get('custom_keyword', '').strip()
    logic = params.get('logic', 'OR') # AND / OR
    display_count = int(params.get('display', 50))
    
    # Date handling
    start_date_str = params.get('start_date') # YYYY-MM-DD
    end_date_str = params.get('end_date')     # YYYY-MM-DD
    
    if start_date_str:
        start_date = datetime.strptime(start_date_str, "%Y-%m-%d").replace(hour=0, minute=0, second=0).astimezone()
    else:
        # Default 14 days
        start_date = (datetime.now() - timedelta(days=14)).astimezone()
        
    if end_date_str:
        end_date = datetime.strptime(end_date_str, "%Y-%m-%d").replace(hour=23, minute=59, second=59).astimezone()
    else:
        end_date = datetime.now().astimezone()

    final_results = {}
    
    # Search targets
    search_list = []
    if logic == 'AND' and custom_keyword:
        for kw in keywords:
            search_list.append(f"{kw} {custom_keyword}")
    else:
        search_list = list(keywords)
        if custom_keyword:
            search_list.append(custom_keyword)

    for query in search_list:
        try:
            encText = urllib.parse.quote(query)
            api_count = 100 
            url = f"https://openapi.naver.com/v1/search/news.json?query={encText}&display={api_count}&sort=date"
            
            req = urllib.request.Request(url)
            req.add_header("X-Naver-Client-Id", client_id)
            req.add_header("X-Naver-Client-Secret", client_secret)
            
            response = urllib.request.urlopen(req)
            if response.getcode() != 200:
                final_results[query] = []
                continue
                
            data = json.loads(response.read().decode('utf-8'))
            items = data.get('items', [])
            
            parsed_items = []
            for item in items:
                p_date = parse_pubdate(item['pubDate'])
                if p_date:
                    if start_date <= p_date <= end_date:
                        parsed_items.append({'original': item, 'date': p_date})
            
            parsed_items.sort(key=lambda x: x['date'], reverse=True)

            processed_items = []
            seen_links = set()
            accepted_titles = [] 

            for p_item in parsed_items:
                if len(processed_items) >= display_count: break
                
                item = p_item['original']
                p_date = p_item['date']
                title = clean_html(item['title'])
                link = item['link']
                
                if link in seen_links: continue
                
                is_duplicate = False
                for acc_title in accepted_titles:
                    if is_similar(title, acc_title, 0.8):
                        is_duplicate = True
                        break
                if is_duplicate: continue

                seen_links.add(link)
                accepted_titles.append(title)
                processed_items.append({
                    'title': title,
                    'link': link,
                    'pubDate': p_date.strftime("%Y-%m-%d %H:%M:%S"),
                    'description': clean_html(item['description'])
                })
            
            final_results[query] = processed_items
        except:
            final_results[query] = []
            
    return final_results

class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()

        CLIENT_ID = os.environ.get("NAVER_CLIENT_ID")
        CLIENT_SECRET = os.environ.get("NAVER_CLIENT_SECRET")
        
        if not CLIENT_ID or not CLIENT_SECRET:
            self.wfile.write(json.dumps({"error": "Missing Keys"}).encode('utf-8'))
            return

        try:
            length = int(self.headers.get('Content-Length', 0))
            params = json.loads(self.rfile.read(length).decode('utf-8'))
            results = process_news_search(CLIENT_ID, CLIENT_SECRET, params)
            self.wfile.write(json.dumps(results).encode('utf-8'))
        except Exception as e:
            self.wfile.write(json.dumps({"error": str(e)}).encode('utf-8'))

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
