"""Check originals in place and the explicitly reviewed integration boundary.

The historical Phase 10.5 package checker intentionally seals old application
bytes too. It stays unchanged and rejects the new Makefile/frontend integration.
This separate sprint checker verifies all original bytes in their worktrees,
and all old integration files except four explicitly declared application edits.
It never excludes historical evidence or Apollo source.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
APP_CHANGES = {'Makefile', 'frontend/README.md', 'frontend/dist/guidance.html',
               'frontend/dist/guidance.mjs'}


def digest(path):
    value = hashlib.sha256()
    with path.open('rb') as stream:
        for part in iter(lambda: stream.read(1048576), b''):
            value.update(part)
    return value.hexdigest()


def check(root, entries, allowed=()):
    problems, changes = [], {}
    for name, expected in entries.items():
        path = root/name
        actual = digest(path) if path.is_file() and not path.is_symlink() else None
        if actual != expected:
            if name in allowed:
                changes[name] = {'before': expected, 'after': actual}
            else:
                problems.append(name)
    return {'checked': len(entries), 'unexpectedChanges': problems,
            'declaredApplicationChanges': changes, 'verified': not problems}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    before = json.loads((HERE/'preservation-before.json').read_text())
    result = {'scope': 'Original worktrees and preserved backend/evidence bytes in integration',
              'originals': {}}
    for label in ('backend', 'frontend'):
        record = before[label]
        root = Path(record['root'])
        current = check(root, record['sha256'])
        for key, argv in [('branch', ['git','branch','--show-current']),
                          ('head', ['git','rev-parse','HEAD']),
                          ('status', ['git','status','--porcelain'])]:
            actual = subprocess.check_output(argv, cwd=root, text=True).strip()
            current[key] = actual
            if actual != record[key].strip():
                current['verified'] = False
                current['unexpectedChanges'].append('Git '+key+' changed')
        result['originals'][label] = current
    result['integration'] = check(ROOT, before['backend']['sha256'], APP_CHANGES)
    from backend.final_assets import verify_science
    result['scientificSeals'] = verify_science()
    result['verified'] = all(r['verified'] for r in result['originals'].values()) and result['integration']['verified']
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result['verified'] else 1)


if __name__ == '__main__':
    # Invocation from any directory remains rooted in the current checkout.
    import sys
    sys.path.insert(0, str(ROOT))
    main()
