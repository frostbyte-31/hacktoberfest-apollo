#!/usr/bin/env python3
"""Browser QA only: first recording request fails, Retry serves the unchanged export.

No backend or evidence is mutated. This server is not an application endpoint.
"""
import argparse
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

DIST = Path(__file__).resolve().parents[2] / 'frontend' / 'dist'


class FailureOnceHandler(SimpleHTTPRequestHandler):
    failures_remaining = 1

    def do_GET(self):
        if urlsplit(self.path).path == '/data/guidance.json' and type(self).failures_remaining:
            type(self).failures_remaining -= 1
            self.send_error(503, 'Deliberately unavailable recording for browser QA')
            return
        super().do_GET()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=4187)
    args = parser.parse_args()
    server = ThreadingHTTPServer(('127.0.0.1', args.port), partial(FailureOnceHandler, directory=str(DIST)))
    print(f'Failure-once browser fixture: http://127.0.0.1:{args.port}/guidance.html', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
