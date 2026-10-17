#!/usr/bin/env python3
"""Exercise real loopback HTTP controls against a fresh native Luminary session."""
import argparse
import datetime
import importlib.util
import json
from pathlib import Path
import shutil
import sys
import threading
import time
import urllib.error
import urllib.request
import uuid

sys.dont_write_bytecode = True
from live_common import HERE, ROOT, digest, new_output, verify_prior, write_json
from analyze import analyze_trace, load_trace


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    output = new_output(args.output or ROOT / '.build/live-control/http-validation' / (
        datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ-') + uuid.uuid4().hex[:8]))
    server = controls = thread = None
    requests = []
    token = None
    started = datetime.datetime.now(datetime.timezone.utc).isoformat()
    try:
        before = verify_prior()
        write_json(output / 'preservation-before.json', before)
        if not before['ok']:
            raise ValueError('Prior evidence changed')
        paths = [Path(__file__), HERE / 'analyze.py', HERE / 'live_common.py',
                 ROOT / 'backend/control_service.py', ROOT / 'backend/native_session.py', ROOT / 'frontend/serve.py']
        hashes = {str(p.relative_to(ROOT)): digest(p) for p in paths}
        write_json(output / 'executed-code-hashes.json', hashes)
        for path in paths:
            target = output / 'executed-code' / path.relative_to(ROOT)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, target)
        sys.path.insert(0, str(ROOT))
        from backend.control_service import ControlService
        from backend.native_session import NativeSession, prepare_assets
        spec = importlib.util.spec_from_file_location('live_actual_http_server', ROOT / 'frontend/serve.py')
        frontend = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(frontend)
        controls = ControlService(prepare=lambda: prepare_assets(output / 'assets'),
            factory=lambda assets: NativeSession(assets, output=output / 'native-session'),
            output_root=output / 'http', pace=True)
        server = frontend.make_server(0, controls=controls)
        base = 'http://127.0.0.1:' + str(server.server_port)
        write_json(output / 'plan.json', {
            'argv': sys.argv, 'started_utc': started, 'base': base,
            'initial_input': {'yaw': 1, 'pitch': -1, 'cycle': 2200000},
            'heartbeat_interval_seconds': .15, 'initial_hold_wall_seconds': .75,
            'followup_input': {'yaw': -1, 'pitch': 0},
            'release': 'Explicit neutral, then followup input expires without heartbeat',
            'note': 'Real handler and worker; only output paths are injected. Tokens are omitted from retained HTTP records.'})
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()

        def request(method, path, body=None, authenticated=True, expected=200):
            headers = {'Origin': base}
            if authenticated and token:
                headers['X-Apollo-Token'] = token
            data = None
            if body is not None:
                data = json.dumps(body, separators=(',', ':'), allow_nan=False).encode()
                headers['Content-Type'] = 'application/json'
            row = {'method': method, 'path': path, 'body': body,
                   'token_present': 'X-Apollo-Token' in headers,
                   'start_utc': datetime.datetime.now(datetime.timezone.utc).isoformat()}
            requests.append(row)
            write_json(output / 'http-requests.json', requests)
            try:
                with urllib.request.urlopen(urllib.request.Request(base+path, data=data, headers=headers, method=method), timeout=10) as response:
                    row['status'] = response.status
                    result = json.load(response)
            except urllib.error.HTTPError as error:
                row['status'] = error.code
                result = json.load(error)
            row['response'] = {**result, 'token': '[ephemeral token omitted]'} if path == '/api/bootstrap' else result
            row['end_utc'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
            write_json(output / 'http-requests.json', requests)
            if row['status'] != expected:
                raise ValueError('Unexpected actual HTTP response ' + str(row['status']) + ' for ' + path)
            return result

        def wait(predicate, seconds=30):
            end = time.monotonic()+seconds
            while True:
                state = request('GET', '/api/status')
                if state['status'] == 'fault':
                    raise ValueError('Actual HTTP native session fault: ' + state['message'])
                if predicate(state):
                    return state
                if time.monotonic() >= end:
                    raise TimeoutError('Actual HTTP/native condition did not occur before deadline')
                time.sleep(.05)

        bootstrap = request('GET', '/api/bootstrap', authenticated=False)
        if not bootstrap['liveEnabled']:
            raise ValueError('Live HTTP capability is disabled')
        token = bootstrap['token']
        request('POST', '/api/session/start', {}, authenticated=False, expected=403)
        start = request('POST', '/api/session/start', {}, expected=202)
        identity = start['sessionId']
        state = wait(lambda value: value['status'] == 'ready')
        if state['frame']['cycle'] != 2200000 or not state['frame']['ready']:
            raise ValueError('The actual UI-ready state is not the original native readiness boundary')
        sequence = 0

        def command(yaw, pitch):
            nonlocal sequence
            current = sequence
            request('POST', '/api/input', {'sessionId': identity, 'sequence': current, 'yaw': yaw, 'pitch': pitch}, expected=202)
            sequence += 1
            return current

        command(1, -1)
        until, heartbeat = time.monotonic()+.75, time.monotonic()+.15
        while time.monotonic() < until:
            state = request('GET', '/api/status')
            if state['status'] == 'fault':
                raise ValueError('Actual native session fault while holding first input')
            if time.monotonic() >= heartbeat:
                command(1, -1)
                heartbeat = time.monotonic()+.15
            time.sleep(.05)
        released = command(0, 0)
        wait(lambda value: value['appliedSequence'] >= released and value['frame']['control']['yaw'] == value['frame']['control']['pitch'] == 0)
        followup = command(-1, 0)
        wait(lambda value: value['appliedSequence'] >= followup and value['frame']['control']['yaw'] == -1)
        wait(lambda value: value['frame']['control']['yaw'] == value['frame']['control']['pitch'] == 0, seconds=5)
        # Let an original gated RHC read observe neutral before freezing motion.
        time.sleep(.25)
        request('POST', '/api/session/stop', {'sessionId': identity}, expected=202)
        wait(lambda value: value['status'] == 'stopped')
        record = request('GET', '/api/record')
        write_json(output / 'downloaded-record.json', record)
        first = next(row for row in record['pilotRequests'] if row['yaw'] or row['pitch'])
        if first.get('native', {}).get('cycle') != 2200000:
            raise ValueError('First actual HTTP deflection did not reach the native readiness boundary')
        trace = output / 'native-session/trace.jsonl'
        result = analyze_trace(trace, 1, -1, fixed_plan=False)
        _, rows = load_trace(trace)
        commands = [row for row in rows if row['ev'] == 'pilot_command']
        if not any(row['yaw'] == -1 and row['pitch'] == 0 for row in commands):
            raise ValueError('Followup HTTP input never reached the authentic hardware input path')
        last = commands[-1]
        automatic = [row for row in rows if row['ev'] == 'neutral' and row['origin'] == 'automatic bounded pulse neutral']
        if not any(row['cycle'] == last['neutral_at'] for row in automatic):
            raise ValueError('Abandoned actual HTTP input did not expire at its native neutral deadline')
        result.update(first_http_input_cycle=first['native']['cycle'],
                      observed_http_pilot_requests=len(record['pilotRequests']),
                      actual_native_pilot_commands=len(commands),
                      explicit_release_sequence=released, expiration_sequence=followup,
                      unauthenticated_start_rejected=True)
        write_json(output / 'analysis.json', result)
        after = verify_prior()
        write_json(output / 'preservation-after.json', after)
        if not after['ok']:
            raise ValueError('Prior evidence changed during HTTP experiment')
        write_json(output / 'completion.json', {'status': 'VERIFIED', 'prior_files_preserved': after['files_checked'],
            'started_utc': started, 'completed_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
            'scope': 'Actual loopback HTTP to original native AGC; simulated attitude and sensor feedback; no descent'})
        print('Actual HTTP live control verified: ' + str(output))
    except BaseException as error:
        write_json(output / 'failure.json', {'error': repr(error), 'status': 'FAILED or incomplete',
            'recorded_utc': datetime.datetime.now(datetime.timezone.utc).isoformat()})
        raise
    finally:
        if controls:
            controls.close()
        if server:
            server.shutdown()
            server.server_close()
        if thread:
            thread.join(timeout=5)


if __name__ == '__main__':
    main()
