from http.server import BaseHTTPRequestHandler
import json
import os
import urllib.request
import urllib.parse
from datetime import datetime, timedelta, timezone
import re
from difflib import SequenceMatcher

# 한국 시간대 설정 (UTC+9)
KST = timezone(timedelta(hours=9))

def clean_html(raw_html):
    if not raw_html: return ""
    cleanr = re.compile('<.*?>')
    cleantext = re.sub(cleanr, '', raw_html)
    cleantext = cleantext.replace('&quot;', '"').replace('&apos;', "'").replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>').replace('&middot;', '·')
    return cleantext

def parse_pubdate(pubdate_str):
    try:
        # 네이버 pubDate 예시: Mon, 05 Jan 2026 15:45:00 +0900
        return datetime.strptime(pubdate_str, "%a, %d %b %Y %H:%M:%S %z")
    except:
        return None

def is_similar(a, b, threshold=0.8):
    if not a or not b: return False
    return SequenceMatcher(None, a, b).ratio() >= threshold

def process_news_search(client_id, client_secret, params):
    keywords = params.get('keywords', [])
    custom_keyword = params.get('custom_keyword', '').strip()
    logic = params.get('logic', 'OR')
    display_count = int(params.get('display', 50))
    
    # 날짜 처리 (KST 기준)
    now_kst = datetime.now(KST)
    start_date_str = params.get('start_date')
    end_date_str = params.get('end_date')
    
    try:
        if start_date_str and start_date_str.strip():
            start_date = datetime.strptime(start_date_str, "%Y-%m-%d").replace(hour=0, minute=0, second=0, tzinfo=KST)
        else:
            start_date = (now_kst - timedelta(days=14)).replace(hour=0, minute=0, second=0)
            
        if end_date_str and end_date_str.strip():
            end_date = datetime.strptime(end_date_str, "%Y-%m-%d").replace(hour=23, minute=59, second=59, tzinfo=KST)
        else:
            end_date = now_kst
    except Exception as e:
        # 파싱 실패 시 기본값 14일 전
        start_date = (now_kst - timedelta(days=14)).replace(hour=0, minute=0, second=0)
        end_date = now_kst

    final_results = {}
    
    # 검색 방식 로직
    search_list = []
    if logic == 'AND':
        combined = " ".join(keywords)
        if custom_keyword:
            combined = (combined + " " + custom_keyword).strip()
        if combined:
            search_list.append(combined)
    else:
        search_list = list(keywords)
        if custom_keyword:
            search_list.append(custom_keyword)

    for query in search_list:
        try:
            encText = urllib.parse.quote(query)
            # 달력 검색을 위해 최대치인 100개를 가져옴
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
                    # KST 기준 시간 비교
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
