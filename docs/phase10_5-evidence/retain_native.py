#!/usr/bin/env python3
"""Package fresh Phase 10.5 native evidence without copying its build tree.

Actual logs retain their original bytes, including observed host paths.
The manifest uses repository-relative source and package-relative references.
JSONL is losslessly compressed; omitted host artifacts receive hashes.
"""
import argparse
import datetime
import gzip
import hashlib
import json
from pathlib import Path
import re
import sys

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def save(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')


def verify(destination):
    manifest = json.loads((destination / 'manifest.json').read_text())
    problems = []
    retained = 0
    for row in manifest['files']:
        if 'retained_path' not in row:
            continue
        path = destination / row['retained_path']
        raw = path.read_bytes()
        if sha(raw) != row['retained_sha256']:
            problems.append(row['retained_path'] + ': packaged hash')
        if row.get('encoding') == 'gzip':
            raw = gzip.decompress(raw)
        if sha(raw) != row['raw_sha256'] or len(raw) != row['raw_bytes']:
            problems.append(row['retained_path'] + ': raw hash/length')
        retained += 1
    checksums = json.loads((destination / 'checksums.json').read_text())
    for name, expected in checksums['sha256'].items():
        if sha((destination / name).read_bytes()) != expected:
            problems.append(name + ': checksums')
    result = {'verified': not problems, 'retained_files_checked': retained,
              'checksums_checked': len(checksums['sha256']), 'problems': problems}
    if problems:
        raise ValueError(json.dumps(result))
    return result


def retain(success, failed, missing, destination):
    for source in (success, failed, missing):
        if ROOT / '.build/phase10_5' not in source.resolve().parents:
            raise ValueError('Inputs must be actual Phase 10.5 .build captures')
    destination.mkdir(parents=True, exist_ok=False)
    files = []

    def add(source, relative, omit=None):
        raw = source.read_bytes()
        row = {'source_path': source.relative_to(ROOT).as_posix(), 'raw_bytes': len(raw),
               'raw_sha256': sha(raw)}
        if omit:
            row['omitted_reason'] = omit
        else:
            target = destination / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            if source.suffix == '.jsonl':
                target = target.with_name(target.name + '.gz')
                packed = gzip.compress(raw, mtime=0)
                row['encoding'] = 'gzip'
            else:
                packed = raw
                row['encoding'] = 'identity'
            with target.open('xb') as stream:
                stream.write(packed)
            row.update(retained_path=target.relative_to(destination).as_posix(),
                       retained_sha256=sha(packed), retained_bytes=len(packed))
        files.append(row)

    def tree(source, prefix):
        for path in sorted(source.rglob('*')):
            if path.is_file():
                omit = 'Host-specific native engine; original source/build commands and hashes retained' if path.suffix in ('.so', '.dylib', '.dll') else None
                add(path, prefix / path.relative_to(source), omit)

    for name, source in [('verified', success), ('failed-build-date', failed)]:
        for path in sorted(source.iterdir()):
            if path.is_file() and path.name != 'baseline.git.tar':
                add(path, Path(name) / path.name)
        baseline = source / 'baseline/.build/phase10_5'
        if (baseline / 'native-validation').exists():
            tree(baseline / 'native-validation', Path(name) / 'native-validation')
        if (baseline / 'focused-tests').exists():
            tree(baseline / 'focused-tests', Path(name) / 'focused-tests')
        # Each actual preparation attempt is retained, including the metadata
        # correction diagnostic. Never copy selected original source or binaries.
        for setup_file in sorted((baseline / 'dependencies/setups').glob('*/setup.json')):
            setup = json.loads(setup_file.read_text())
            label = setup_file.parent.name
            tree(setup_file.parent, Path(name) / 'preparation' / label)
            assembly = Path(setup['assembly'])
            for filename in ('commands.json', 'build-summary.json', 'compiler-version.stdout', 'compiler-version.stderr',
                             'build-yayul.stdout', 'build-yayul.stderr', 'assemble.stderr', 'source-before.json', 'source-after.json'):
                add(assembly / filename, Path(name) / 'preparation' / label / 'assembly' / filename)
            for key in ('listing', 'symbols', 'rope', 'symtab'):
                path = Path(setup[key])
                add(path, Path(name) / 'unused', 'Reproducible original generated artifact; SHA recorded, no duplicate source listing or binaries')
    tree(missing, Path('missing-historical-evidence'))
    counts = {}
    for path in sorted((success / 'baseline/.build/phase10_5/focused-tests').glob('*.stderr')):
        text = path.read_text()
        found = re.search(r'^Ran (\d+) tests? in ', text, re.MULTILINE)
        if found:
            counts[path.stem] = {'tests': int(found.group(1)), 'passed': '\nOK\n' in text,
                                 'failures': 0 if '\nOK\n' in text else 'See actual log'}
    summary = {'classification': 'VERIFIED fresh original native execution; UI uses recorded authentic replay',
               'baseline_revision': '6859637ae8dcb1041db3944489d0f909ed58429f',
               'focused_tests': counts, 'focused_tests_total': sum(v['tests'] for v in counts.values()),
               'canonical_raw_traces_match': json.loads((success / 'completion.json').read_text())['canonical_trace_matches'],
               'historical_missing_errors_remain': 3, 'powered_descent': 'NOT RUN',
               'reproduce': ['python3 -B tools/demo/demo.py reproduce',
                             'python3 -B tools/demo/demo.py reproduce --archive /path/to/pinned-upstream.tar.gz'],
               'path_policy': 'Manifest references are portable. Actual captured command/log bytes preserve observed host paths; they are evidence, not configuration.',
               'build_date_remedy': 'SOURCE_DATE_EPOCH=1792195200 gives unchanged yaYUL its retained compile-date banner. Original listing/symbol checks remain exact.',
               'upstream_source_and_build_tree': 'Not copied. Original pinned source archive and each source hash, compiler commands, and artifact checksums remain recorded.'}
    save(destination / 'summary.json', summary)
    manifest = {'created_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
                'scope': 'Fresh Phase 10.5 execution and build-date failure diagnosis; no historical evidence modified',
                'files': files}
    save(destination / 'manifest.json', manifest)
    save(destination / 'checksums.json', {'scope': 'Retained package files, excluding this checksum inventory',
         'sha256': {p.relative_to(destination).as_posix(): sha(p.read_bytes())
                    for p in sorted(destination.rglob('*')) if p.is_file()}})
    return verify(destination)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--success', type=Path, default=ROOT / '.build/phase10_5/reproduction/verified')
    parser.add_argument('--failed', type=Path, default=ROOT / '.build/phase10_5/reproduction/final')
    parser.add_argument('--missing', type=Path, default=ROOT / '.build/phase10_5/missing-evidence-with-archives')
    parser.add_argument('--output', type=Path, default=HERE / 'native')
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    if args.output.resolve().parent != HERE or args.output.is_symlink():
        raise ValueError('New evidence packaging belongs directly under docs/phase10_5-evidence')
    result = verify(args.output) if args.check else retain(args.success.resolve(), args.failed.resolve(), args.missing.resolve(), args.output.resolve())
    print(json.dumps(result, indent=2, sort_keys=True))
