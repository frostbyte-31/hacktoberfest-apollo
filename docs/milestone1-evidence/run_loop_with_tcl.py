#!/usr/bin/env python3
"""GPL-2.0-or-later. Select Tcl for the unchanged Phase 5 integration runner.

Only the dependency-launch command changes. No emulator, model, fixture or
feedback computation is copied into this adapter.
"""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import types

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
PRIOR = ROOT / 'docs/phase5-evidence'


def plant_command(requested, tcl, source):
    expected = ['nix', 'shell', 'nixpkgs#tcl', '-c', 'tclsh',
                str(PRIOR / 'plant_server.tcl'), str(source)]
    if list(requested) != expected:
        raise ValueError('Unexpected legacy dependency command')
    return [str(tcl), str(PRIOR / 'plant_server.tcl'), str(source)]


def validate_destinations(output, launch_record):
    for path in (output, Path(str(output) + '.tcl.stderr'), launch_record):
        destination = path.resolve()
        if destination.exists():
            raise ValueError('Output files must not already exist')
        if destination == ROOT or ROOT in destination.parents:
            build = ROOT / '.build'
            if destination == build or build not in destination.parents:
                raise ValueError('Use .build or external scratch; retained evidence is read-only')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tcl', type=Path, required=True)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--library', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--mode', choices=('closed', 'feedback_off'), required=True)
    parser.add_argument('--launch-record', type=Path, required=True)
    args = parser.parse_args()
    tcl, source = args.tcl.resolve(), args.source.resolve()
    validate_destinations(args.output, args.launch_record)
    spec = importlib.util.spec_from_file_location('retained_phase5_loop', PRIOR / 'run_loop.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    def start_plant(command, **kwargs):
        actual = plant_command(command, tcl, source)
        args.launch_record.write_text(json.dumps({
            'adapter': str(Path(__file__).resolve()),
            'retained_runner': str(PRIOR / 'run_loop.py'),
            'requested_legacy_command': command,
            'actual_command': actual,
            'change': 'Dependency executable selection only; no Nix process is run.'
        }, indent=2) + '\n')
        environment = dict(os.environ)
        for key in ('TCL_LIBRARY', 'TCLLIBPATH', 'LD_LIBRARY_PATH',
                    'DYLD_LIBRARY_PATH', 'DYLD_FALLBACK_LIBRARY_PATH'):
            environment.pop(key, None)
        environment.update(LC_ALL='C', LANG='C', TZ='UTC')
        return subprocess.Popen(actual, env=environment, **kwargs)

    # Override only this loaded module's dependency interface, not subprocess
    # globally. The retained runner otherwise executes its original main().
    module.subprocess = types.SimpleNamespace(Popen=start_plant, PIPE=subprocess.PIPE)
    module.sys = types.SimpleNamespace(argv=[str(PRIOR / 'run_loop.py'), str(source),
        str(args.library.resolve()), str(args.output.resolve()), args.mode])
    module.main()


if __name__ == '__main__':
    main()
