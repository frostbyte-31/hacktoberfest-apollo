#!/usr/bin/env python3
"""Run fresh P51, exact replay and mark-interrupt disconnect, then analyze."""
import argparse
import datetime
import json
import os
from pathlib import Path
import subprocess
import sys
import uuid

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
from run_alignment import sha, save, verify_prior


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--setup', type=Path, required=True)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    output = (args.output or ROOT/'.build/phase9/validation'/(
        datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ-')+uuid.uuid4().hex[:8])).resolve()
    if ROOT in output.parents and ROOT/'.build' not in output.parents:
        raise ValueError('Fresh experiments must use .build or an external scratch directory')
    output.mkdir(parents=True, exist_ok=False)
    commands = []
    frozen = {str(path.relative_to(ROOT)): sha(path) for path in [HERE/'run_alignment.py', HERE/'hardware_bridge.c', HERE/'analyze.py', HERE/'prepare.py', HERE/'rebuild_source.py', Path(__file__)]}
    save(output/'code-before.json', frozen)
    before = verify_prior()
    save(output/'preservation-before.json', before)
    if not before['ok']:
        raise ValueError('Earlier evidence changed')

    def run(label, argv):
        row = {'label': label, 'argv': argv, 'cwd': str(ROOT), 'started_utc': datetime.datetime.now(datetime.timezone.utc).isoformat()}
        commands.append(row)
        save(output/'commands.json', commands)
        with (output/(label+'.stdout')).open('w') as stdout, (output/(label+'.stderr')).open('w') as stderr:
            result = subprocess.run(argv, cwd=ROOT, stdout=stdout, stderr=stderr, env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1'))
        row.update(exit=result.returncode, ended_utc=datetime.datetime.now(datetime.timezone.utc).isoformat())
        save(output/'commands.json', commands)
        if result.returncode:
            raise ValueError('Actual '+label+' failed; preserve this output directory')
        print(label+' exit0', flush=True)

    try:
        for case in ('final', 'repeat', 'mark-irq-off'):
            argv = [sys.executable, '-B', str(HERE/'run_alignment.py'), '--setup', str(args.setup.resolve()), '--output', str(output/case)]
            if case == 'mark-irq-off':
                argv.append('--no-mark-irq')
            run(case, argv)
        run('analysis', [sys.executable, '-B', str(HERE/'analyze.py'), '--run', str(output/'final'), '--repeat', str(output/'repeat'), '--negative', str(output/'mark-irq-off'), '--output', str(output/'analysis.json')])
        after = verify_prior()
        save(output/'preservation-after.json', after)
        changed = [name for name, digest in frozen.items() if sha(ROOT/name) != digest]
        if not after['ok'] or changed:
            raise ValueError('Inputs changed during batch: '+repr(changed))
        save(output/'completion.json', {'classification': 'VERIFIED P51 alignment sets original REFSMFLG; P63 passes R02 then aborts01406; no powered descent',
            'prior_files_preserved': after['files_checked'], 'exact_replay': True, 'source_files_unchanged': True,
            'completed_utc': datetime.datetime.now(datetime.timezone.utc).isoformat()})
        print('Phase9 final native validation: '+str(output))
    except BaseException as error:
        save(output/'failure.json', {'error': repr(error), 'utc': datetime.datetime.now(datetime.timezone.utc).isoformat()})
        raise


if __name__ == '__main__':
    main()
