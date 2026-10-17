#!/usr/bin/env python3
"""Fresh negative baseline, original mission update, exact replay and controls."""
import argparse
import datetime
import json
from pathlib import Path
import subprocess
import sys
import uuid
sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
from run_mission import preserve, p9


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--setup', type=Path, required=True)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    output = (args.output or ROOT/'.build/phase10/validation'/uuid.uuid4().hex[:10]).resolve()
    if ROOT/'.build' not in output.parents:
        raise ValueError('Fresh validation belongs under .build, not retained historical evidence')
    output.mkdir(parents=True, exist_ok=False)
    before = preserve()
    p9.save(output/'preservation-before.json', before)
    if not before['ok']:
        raise ValueError('Earlier tracked input changed')
    sources = [HERE/name for name in ('run_mission.py', 'analyze.py', 'validate.py')]
    sources += list((HERE/'math').glob('*.py'))+list((HERE/'configs').glob('*.json'))
    frozen = {str(p.relative_to(ROOT)): p9.sha(p) for p in sources}
    p9.save(output/'code-before.json', frozen)
    commands = []

    def run(name, argv):
        row = {'name': name, 'argv': argv, 'cwd': str(ROOT), 'started_utc': datetime.datetime.now(datetime.timezone.utc).isoformat()}
        commands.append(row)
        p9.save(output/'commands.json', commands)
        with (output/(name+'.stdout')).open('w') as out, (output/(name+'.stderr')).open('w') as err:
            result = subprocess.run(argv, cwd=ROOT, stdout=out, stderr=err)
        row.update(exit=result.returncode, ended_utc=datetime.datetime.now(datetime.timezone.utc).isoformat())
        p9.save(output/'commands.json', commands)
        print(name+' exit'+str(result.returncode), flush=True)
        if result.returncode:
            raise ValueError('Failed '+name+'; preserve complete outputs')

    try:
        run('phase9-baseline', [sys.executable, '-B', str(ROOT/'docs/phase9-evidence/validate.py'),
            '--setup', str(args.setup.resolve()), '--output', str(output/'phase9-baseline')])
        for name, config in [('final', 'mission-15km'), ('repeat', 'mission-15km'), ('altitude-16km', 'mission-16km'), ('missing-site', 'missing-site')]:
            run(name, [sys.executable, '-B', str(HERE/'run_mission.py'), '--setup', str(args.setup.resolve()),
                '--config', str(HERE/'configs'/(config+'.json')), '--output', str(output/name)])
        run('analysis', [sys.executable, '-B', str(HERE/'analyze.py'), '--runs', str(output),
            '--baseline-analysis', str(output/'phase9-baseline/analysis.json'), '--output', str(output/'analysis.json')])
        for name in ('final', 'altitude-16km'):
            run(name+'-independent-math', [sys.executable, '-B', str(HERE/'math/inspect_native.py'), '--run', str(output/name),
                '--output', str(output/(name+'-independent-math.json'))])
        after = preserve()
        changed = [name for name, expected in frozen.items() if p9.sha(ROOT/name) != expected]
        p9.save(output/'preservation-after.json', after)
        if not after['ok'] or changed:
            raise ValueError('Inputs changed during batch: '+repr(changed))
        p9.save(output/'completion.json', {'classification': 'VERIFIED bounded original P63 numerical guidance, not powered descent',
                'prior_files_checked': after['files_checked'], 'input_sources_unchanged': True})
    except BaseException as error:
        p9.save(output/'failure.json', {'error': repr(error)})
        raise


if __name__ == '__main__':
    main()
