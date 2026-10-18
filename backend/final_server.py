"""Versioned shared-mission routes beside the unchanged live attitude API."""
from functools import partial
import importlib.util
import json
from pathlib import Path
import re
from urllib.parse import urlsplit

from backend.control_service import ControlError, ControlService
from backend.mission_service import MissionService

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('apollo_existing_http', ROOT/'frontend/serve.py')
existing = importlib.util.module_from_spec(spec)
spec.loader.exec_module(existing)
MISSION = re.compile(r'^/api/v1/missions/([0-9a-f]{16})(?:/(join|command))?$')


def unique_object(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError('Duplicate JSON key')
        value[key] = item
    return value


class FinalHandler(existing.ApolloHandler):
    def _origin(self, mutation=False):
        path = urlsplit(self.path).path
        if (not mutation and not path.startswith('/api/')
                and self.command in ('GET', 'HEAD')
                and self.headers.get('Sec-Fetch-Mode') == 'navigate'
                and self.headers.get('Sec-Fetch-Dest') == 'document'):
            # Normal links/extensions may initiate a cross-site document
            # navigation. Only static documents get this narrow exception;
            # API Origin, token and fetch-site checks remain unchanged.
            host = self.headers.get('Host', '')
            if host not in ('127.0.0.1:'+str(self.server.server_port),
                            'localhost:'+str(self.server.server_port)):
                raise ControlError(421, 'This service accepts its loopback host only.')
            return
        return super()._origin(mutation=mutation)

    def _body(self):
        if self.headers.get('Transfer-Encoding'):
            raise ControlError(400, 'Transfer encoding is unsupported.')
        if self.headers.get('Content-Type', '').split(';')[0].strip() != 'application/json':
            raise ControlError(415, 'Use application/json.')
        try:
            length = int(self.headers.get('Content-Length', ''))
        except ValueError:
            raise ControlError(411, 'Content-Length is required.')
        if not 0 < length <= 8192:
            raise ControlError(413, 'Crew command exceeds the bounded request size.')
        try:
            raw = self.rfile.read(length)
            if len(raw) != length:
                raise ValueError('Incomplete body')
            value = json.loads(raw, object_pairs_hook=unique_object,
                parse_constant=lambda _: (_ for _ in ()).throw(ValueError('Nonfinite JSON')))
            if not isinstance(value, dict):
                raise ValueError('An object is required')
            return value
        except TimeoutError:
            raise ControlError(408, 'Request body timed out.')
        except (ValueError, UnicodeError):
            raise ControlError(400, 'A valid bounded JSON object is required.')

    def do_HEAD(self):
        try:
            self._origin()
            if urlsplit(self.path).path.startswith('/api/'):
                raise ControlError(405, 'Use GET for API observations.')
            return super().do_HEAD()
        except ControlError as error:
            self._json(error.status, {'error': str(error)})

    def do_GET(self):
        path = urlsplit(self.path).path
        if not path.startswith('/api/v1/'):
            return super().do_GET()
        try:
            self._origin()
            if path == '/api/v1/capabilities':
                result = self.server.missions.capabilities()
                result.update(token=self.server.control_token, dependencyError=self.server.assets_error)
                self._json(200, result)
                return
            match = MISSION.fullmatch(path)
            if match and match.group(2) is None:
                self._json(200, self.server.missions.snapshot(match.group(1),
                           self.headers.get('X-Apollo-Participant')))
                return
            raise ControlError(404, 'Unknown mission API route.')
        except ControlError as error:
            self._json(error.status, {'error': str(error)})

    def do_POST(self):
        path = urlsplit(self.path).path
        if not path.startswith('/api/v1/'):
            return super().do_POST()
        try:
            self._origin(mutation=True)
            self._token()
            value = self._body()
            if path == '/api/v1/missions':
                result = self.server.missions.create(value)
            else:
                match = MISSION.fullmatch(path)
                if not match:
                    raise ControlError(404, 'Unknown mission API route.')
                if match.group(2) == 'join':
                    result = self.server.missions.join(match.group(1), value)
                elif match.group(2) == 'command':
                    result = self.server.missions.command(match.group(1),
                                   self.headers.get('X-Apollo-Participant'), value)
                else:
                    raise ControlError(404, 'Unknown mission action.')
            self._json(200, result)
        except ControlError as error:
            self._json(error.status, {'error': str(error)})
        except (ValueError, TypeError) as error:
            self._json(400, {'error': 'Invalid mission request: '+str(error)})
        except Exception:
            # Keep unavailable native dependencies explicit; never publish a
            # fabricated frame or leak provider configuration through errors.
            self._json(503, {'error': 'The mission could not execute. Check the local server diagnostics; recordings remain available.'})


def make_server(port=4173, assets=None, assets_error=None, missions=None, ai_provider=None):
    controls = ControlService(prepare=(lambda: assets) if assets else None)
    # The sourced checklist is Python-only. Missing compiled assets disable
    # native inputs without disabling that independent training service.
    server = existing.make_server(port, controls=controls, replay_only=False,
                                  native_enabled=assets is not None)
    server.RequestHandlerClass = partial(FinalHandler, directory=str(ROOT/'frontend/dist'))
    server.missions = missions or MissionService(assets=assets, ai_provider=ai_provider)
    server.assets_error = assets_error
    return server


def close_server(server):
    server.missions.close()
    server.controls.close()
    server.server_close()
