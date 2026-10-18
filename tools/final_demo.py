#!/usr/bin/env python3
"""One local launch for preserved AGC demos and the shared educational lab."""
import argparse
import errno
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.dont_write_bytecode = True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=4173)
    parser.add_argument('--recorded-only', action='store_true',
                        help='Skip native dependencies; keep recorded experiences and Python-only checklist training')
    parser.add_argument('--bootstrap-runtime', action='store_true',
                        help='Build the original locked Tcl if no verified runtime cache exists')
    args = parser.parse_args()
    if not 0 <= args.port <= 65535:
        parser.error('--port must be between 0 and 65535')
    from backend.final_assets import prepare_demo_assets, verify_science
    print('Apollo 11 · final mission laboratory', flush=True)
    verified = verify_science()
    print('Original Luminary rope and sealed Phases 10–12 evidence verified.', flush=True)
    guidance_check = subprocess.run([sys.executable, '-B', str(ROOT/'frontend/tools/export_guidance.py'), '--check'],
                                    cwd=ROOT, text=True, capture_output=True)
    if guidance_check.returncode:
        parser.error('Recorded guidance export failed verification. Run python3 -B frontend/tools/export_guidance.py --check for diagnostics.')
    from backend.propulsion_recording import build_recording, verify_export
    recording = ROOT/'frontend/dist/data/propulsion-lab.json'
    if not recording.is_file():
        parser.error('Authentic propulsion recording is missing or stale. Run python3 -B -m backend.propulsion_recording.')
    try:
        comparison = verify_export(recording.read_text(), build_recording())
    except ValueError:
        parser.error('Authentic propulsion recording differs from sealed source. Run python3 -B -m backend.propulsion_recording --check for diagnostics.')
    print('Recorded propulsion samples verified against actual raw traces.', flush=True)
    print('Propulsion export verification: '+json.dumps(comparison), flush=True)
    assets, error = None, None
    if not args.recorded_only:
        try:
            print('Checking locked runtime and preparing original attitude/engine assets…', flush=True)
            assets = prepare_demo_assets(bootstrap=args.bootstrap_runtime)
        except Exception as failure:
            error = str(failure)
            print('Native/physical modes unavailable: '+error, flush=True)
            print('Recorded guidance and propulsion remain available. See --bootstrap-runtime or make runtime.', flush=True)
    from backend.final_server import make_server, close_server
    from backend.crew_ai import provider_from_environment
    try:
        provider = provider_from_environment()
    except ValueError:
        provider = None
        print('Model configuration incomplete/invalid; LLM seats disabled.', flush=True)
    try:
        server = make_server(args.port, assets=assets, assets_error=error, ai_provider=provider)
    except OSError as failure:
        if failure.errno == errno.EADDRINUSE:
            parser.error('Port is already occupied; no process was stopped. Choose --port 4180.')
        raise
    print('Open: http://127.0.0.1:{}/'.format(server.server_port), flush=True)
    print('Undocking checklist: /play.html · shared educational flight: /mission.html', flush=True)
    print('Recorded guidance: /guidance.html · existing attitude controls: /attitude-replay.html', flush=True)
    print('Mode: '+('verified native attitude + independent educational physics + authentic recordings + checklist training' if assets else 'recorded authentic execution + Python-only checklist training; native flight modes unavailable'), flush=True)
    print('Ctrl+C shuts down owned workers and physical model processes.', flush=True)
    print('Model crew: '+('flight lab unavailable until verified physical dependencies are prepared'
        if not assets else 'configured server-side; requests occur only for selected model seats'
        if provider else 'not configured; labeled deterministic crew available'), flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        close_server(server)


if __name__ == '__main__':
    main()
