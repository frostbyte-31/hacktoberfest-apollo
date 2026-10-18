"""Exercise the actual offline launcher, occupied-port handling and shutdown.

Only processes created by this check are signaled. No emulator or model is
substituted; recorded-only mode must explicitly disable native capabilities.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import selectors
import signal
import subprocess
import sys
import time
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[2]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    command = [sys.executable, '-B', 'tools/final_demo.py', '--recorded-only', '--port', '0']
    process = subprocess.Popen(command, cwd=ROOT, stdout=subprocess.PIPE,
                               stderr=subprocess.STDOUT, bufsize=0)
    capture = bytearray()
    result = {'command': command, 'cwd': str(ROOT), 'checks': {}}
    try:
        selector = selectors.DefaultSelector()
        selector.register(process.stdout, selectors.EVENT_READ)
        deadline = time.monotonic()+45
        port = None
        while time.monotonic() < deadline and port is None:
            for key, _ in selector.select(.2):
                part = key.fileobj.read(4096)
                if not part:
                    raise RuntimeError('Launcher exited before serving')
                capture.extend(part)
                match = re.search(rb'Open: http://127.0.0.1:(\d+)/mission.html', capture)
                if match:
                    port = int(match.group(1))
        if port is None:
            raise RuntimeError('Launcher did not become ready within 45 seconds')
        base = 'http://127.0.0.1:'+str(port)
        def get(path):
            with urlopen(base+path, timeout=8) as response:
                return response.read()
        capability = json.loads(get('/api/v1/capabilities'))
        (args.output/'capabilities.json').write_text(json.dumps(
            {k: v for k, v in capability.items() if k != 'token'}, indent=2)+'\n')
        caps = capability['capabilities']
        assert caps['recordedGuidance'] and caps['recordedPropulsion']
        assert not caps['physicsLab'] and not caps['liveAuthenticAttitude']
        result['checks']['offline_capabilities_honest'] = True
        pages = {}
        for name in ('mission.html', 'guidance.html', 'index.html'):
            actual = get('/'+name)
            assert actual == (ROOT/'frontend/dist'/name).read_bytes()
            pages[name] = hashlib.sha256(actual).hexdigest()
        result['checks']['three_real_app_documents_served'] = pages
        second = command[:-1]+[str(port)]
        occupied = subprocess.run(second, cwd=ROOT, capture_output=True, timeout=45)
        (args.output/'occupied.stdout').write_bytes(occupied.stdout)
        (args.output/'occupied.stderr').write_bytes(occupied.stderr)
        assert occupied.returncode != 0 and b'Port is already occupied' in occupied.stderr
        assert get('/mission.html') == (ROOT/'frontend/dist/mission.html').read_bytes()
        result['occupiedCommand'] = second
        result['checks']['occupied_port_does_not_stop_owner'] = True
    finally:
        if process.poll() is None:
            process.send_signal(signal.SIGINT)
        try:
            tail, _ = process.communicate(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            tail, _ = process.communicate()
            raise RuntimeError('Owned launcher failed to shut down after SIGINT')
        capture.extend(tail)
        (args.output/'launcher.stdout').write_bytes(capture)
        result['launcherExitCode'] = process.returncode
        result['checks']['owned_launcher_shutdown_clean'] = process.returncode == 0
        (args.output/'result.json').write_text(json.dumps(result, indent=2)+'\n')
    assert result['launcherExitCode'] == 0
    print(json.dumps(result))


if __name__ == '__main__':
    main()
