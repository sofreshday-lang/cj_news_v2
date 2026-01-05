import http.server
import socketserver
import json
import os
import sys
from pathlib import Path

# Add the current directory to sys.path so we can import api.news
sys.path.append(os.getcwd())

try:
    from api.news import handler
except ImportError:
    # If starting from root
    from news_monitor_final.api.news import handler

PORT = 8000

class LocalDevHandler(http.server.SimpleHTTPRequestHandler):
    def do_POST(self):
        if self.path == '/api/news':
            # Create an instance of the Vercel handler-like class
            # and call its do_POST
            handler.do_POST(self)
        else:
            super().do_POST()

    def do_OPTIONS(self):
        if self.path == '/api/news':
            handler.do_OPTIONS(self)
        else:
            super().do_OPTIONS()

    def do_GET(self):
        # Serve index.html for root
        if self.path == '/':
            self.path = '/index.html'
        return super().do_GET()

def load_env():
    # Attempt to load from .env file in parent or current dir
    env_paths = [Path('.env'), Path('..') / '.env', Path('../..') / '.env']
    for env_path in env_paths:
        if env_path.exists():
            with open(env_path, 'r', encoding='utf-8') as f:
                for line in f:
                    if '=' in line and not line.startswith('#'):
                        key, value = line.strip().split('=', 1)
                        os.environ[key] = value
            print(f"Loaded environment variables from {env_path.absolute()}")
            return True
    return False

if __name__ == "__main__":
    load_env()
    
    # Check for keys
    if not os.environ.get("NAVER_CLIENT_ID"):
        print("Warning: NAVER_CLIENT_ID not found in environment.")
    
    with socketserver.TCPServer(("", PORT), LocalDevHandler) as httpd:
        print(f"Server started at http://localhost:{PORT}")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nStopping server...")
            httpd.shutdown()
