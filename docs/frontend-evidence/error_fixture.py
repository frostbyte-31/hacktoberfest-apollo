#!/usr/bin/env python3
"""UI fault fixture: first recording GET returns 503, retry serves actual data.

Not an AGC/backend substitute. Serves unchanged application files on loopback;
all /api requests return 404 to exercise recorded-mode operation without a backend.
"""
import argparse
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit
ROOT = Path(__file__).resolve().parents[2]
class Handler(SimpleHTTPRequestHandler):
    def do_GET(self):
        path = urlsplit(self.path).path
        if path == '/data/guidance.json':
            self.server.recording_requests += 1
            if self.server.recording_requests == 1:
                self.send_error(503, 'Intentional UI-test recording outage')
                return
        if path.startswith('/api/'):
            self.send_error(404, 'No backend in this UI fault fixture')
            return
        super().do_GET()
if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--port', type=int, default=4184)
    args = p.parse_args()
    server = ThreadingHTTPServer(('127.0.0.1', args.port), partial(Handler, directory=str(ROOT / 'frontend/dist')))
    server.recording_requests = 0
    print('UI fault fixture only: http://127.0.0.1:{}/guidance.html'.format(server.server_port), flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
