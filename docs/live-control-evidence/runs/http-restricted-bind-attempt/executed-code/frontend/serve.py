#!/usr/bin/env python3
"""Loopback frontend and bounded live AGC inputs; no descent interface."""
import argparse
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import secrets
import sys
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.dont_write_bytecode = True
from backend.control_service import ControlError, ControlService


class ApolloHandler(SimpleHTTPRequestHandler):
    def setup(self):
        super().setup()
        self.connection.settimeout(5)

    def _json(self, status, value):
        raw = json.dumps(value, separators=(',', ':'), allow_nan=False).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(raw)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.end_headers()
        self.wfile.write(raw)

    def _origin(self, mutation=False):
        host = self.headers.get('Host', '')
        allowed = {'127.0.0.1:{}'.format(self.server.server_port),
                   'localhost:{}'.format(self.server.server_port)}
        if host not in allowed:
            raise ControlError(421, 'This service accepts its loopback host only.')
        origin = self.headers.get('Origin')
        if (mutation and not origin) or (origin is not None and origin != 'http://' + host):
            raise ControlError(403, 'A matching same-origin request is required.')
        if self.headers.get('Sec-Fetch-Site', 'none') not in ('same-origin', 'none'):
            raise ControlError(403, 'Cross-site access is not permitted.')

    def _token(self):
        token = self.headers.get('X-Apollo-Token', '')
        if not token.isascii() or not secrets.compare_digest(token, self.server.control_token):
            raise ControlError(403, 'Missing or invalid local control token.')

    def do_GET(self):
        try:
            self._origin()
            path = urlsplit(self.path).path
            if path == '/api/bootstrap':
                self._json(200, {'liveEnabled': self.server.live_enabled,
                                 'token': self.server.control_token if self.server.live_enabled else None,
                                 'axes': ['yaw', 'pitch'], 'deflectionCounts': 20,
                                 'pulseLeaseSeconds': .5, 'scope': 'Bounded attitude only; no powered descent.'})
            elif path == '/api/status':
                self._json(200, self.server.controls.snapshot())
            elif path == '/api/record':
                self._token()
                self._json(200, self.server.controls.record())
            elif path.startswith('/api/'):
                raise ControlError(404, 'Unknown local API route.')
            else:
                super().do_GET()
        except ControlError as error:
            self._json(error.status, {'error': str(error)})

    def do_POST(self):
        try:
            self._origin(mutation=True)
            self._token()
            if not self.server.live_enabled:
                raise ControlError(409, 'Live control is disabled on this replay-only server.')
            if self.headers.get('Transfer-Encoding'):
                raise ControlError(400, 'Transfer-encoded requests are not accepted.')
            if self.headers.get('Content-Type', '').split(';')[0].strip() != 'application/json':
                raise ControlError(415, 'Use application/json.')
            try:
                length = int(self.headers.get('Content-Length', ''))
            except ValueError:
                raise ControlError(411, 'A bounded Content-Length is required.')
            if not 0 < length <= 1024:
                raise ControlError(413, 'Controller request is too large.')
            try:
                raw = self.rfile.read(length)
                if len(raw) != length:
                    raise ValueError('Incomplete body')
                def unique_object(pairs):
                    value = {}
                    for key, item in pairs:
                        if key in value:
                            raise ValueError('Duplicate request key')
                        value[key] = item
                    return value
                value = json.loads(raw, object_pairs_hook=unique_object,
                                   parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
            except TimeoutError:
                raise ControlError(408, 'Controller request body timed out.')
            except (ValueError, UnicodeError):
                raise ControlError(400, 'Invalid JSON request.')
            if not isinstance(value, dict):
                raise ControlError(400, 'Request must be a JSON object.')
            path = urlsplit(self.path).path
            if path == '/api/session/start' and not value:
                self._json(202, self.server.controls.start())
            elif path == '/api/input' and set(value) == {'sessionId', 'sequence', 'yaw', 'pitch'}:
                self._json(202, self.server.controls.command(value['sessionId'], value['sequence'], value['yaw'], value['pitch']))
            elif path == '/api/session/stop' and set(value) == {'sessionId'}:
                self._json(202, self.server.controls.stop(value['sessionId']))
            elif path in ('/api/session/start', '/api/input', '/api/session/stop'):
                raise ControlError(400, 'Request fields do not match the bounded input contract.')
            else:
                raise ControlError(404, 'Unknown local API route.')
        except ControlError as error:
            self._json(error.status, {'error': str(error)})

    def do_OPTIONS(self):
        self._json(403, {'error': 'Cross-origin control is not supported.'})


def make_server(port=4173, controls=None, replay_only=False):
    handler = partial(ApolloHandler, directory=str(ROOT / 'frontend/dist'))
    server = ThreadingHTTPServer(('127.0.0.1', port), handler)
    server.control_token = secrets.token_urlsafe(32)
    server.controls = controls or ControlService()
    server.live_enabled = not replay_only
    return server


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=4173)
    parser.add_argument('--replay-only', action='store_true')
    args = parser.parse_args()
    server = make_server(args.port, replay_only=args.replay_only)
    print('Apollo 11 Attitude Lab', flush=True)
    print('Local: http://127.0.0.1:{}/'.format(server.server_port), flush=True)
    print('Live control: {}'.format('disabled' if args.replay_only else 'available; native startup begins on request'), flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.controls.close()
        server.server_close()


if __name__ == '__main__':
    main()
