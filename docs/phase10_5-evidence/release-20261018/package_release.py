#!/usr/bin/env python3
"""Package completed final checks into a new release directory; never run tests.

This deliberately leaves every earlier report, evidence file and seal untouched.
Run only after all three release check processes have completed successfully.
"""
import datetime
import gzip
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import subprocess
import sys

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
BUILD = ROOT / '.build/phase10_5/release-20261018'
DEST = ROOT / 'docs/phase10_5-evidence/release-20261018'
BASE = BUILD / 'native/baseline/.build/phase10_5'


def read(path):
    return json.loads(path.read_text())


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def save(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + '\n')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def json_objects(text):
    decoder = json.JSONDecoder()
    offset = 0
    while offset < len(text):
        start = text.find('{', offset)
        if start < 0:
            break
        try:
            value, length = decoder.raw_decode(text[start:])
        except ValueError:
            offset = start + 1
            continue
        offset = start + length
        if isinstance(value, dict):
            yield value


def unittest_counts(path):
    text = path.read_text()
    values = re.findall(r'^Ran (\d+) tests? in ', text, re.MULTILINE)
    require(values and len(re.findall(r'^OK$', text, re.MULTILINE)) == len(values),
            'Incomplete or unsuccessful unittest log: ' + str(path))
    require(not re.search(r'^FAILED|^ERROR:|^FAIL:', text, re.MULTILINE),
            'Unexpected unittest failure: ' + str(path))
    return sum(map(int, values))


def node_counts(path):
    text = path.read_text()
    def number(field):
        values = re.findall(r'^(?:#|ℹ) ' + field + r' (\d+)$', text, re.MULTILINE)
        require(len(values) == 1, 'Missing or duplicate Node summary: ' + str(path))
        return int(values[0])
    count = number('tests')
    require(number('pass') == count and number('fail') == 0 and number('skipped') == 0,
            'Unexpected Node result: ' + str(path))
    return count


def main():
    require(not DEST.exists(), 'Refusing to overwrite existing release evidence')
    native = read(BUILD / 'native/completion.json')
    require(native.get('verified') and all(native['canonical_trace_matches'].values()),
            'Native run incomplete or did not match canonical traces')
    regression = read(BUILD / 'regressions/record.json')
    require(regression.get('passed') and not regression.get('changed_during_checks')
            and len(regression['commands']) == 3
            and all(row.get('returncode') == 0 for row in regression['commands']),
            'Regression batch incomplete or failed')
    fresh = read(BUILD / 'new-tests/record.json')
    require(len(fresh['commands']) == 7 and all(row.get('exit') == 0 for row in fresh['commands']),
            'New checks incomplete or failed')
    native_commands = read(BASE / 'focused-tests/commands.json')['commands']
    require(len(native_commands) == 4 and all(row.get('exit') == 0 for row in native_commands),
            'Original focused test batch incomplete or failed')
    for name in ('git-archive', 'prepare', 'native-validation', 'focused-tests'):
        require(read(BUILD / 'native' / (name + '.command.json')).get('exit') == 0,
                'Native command incomplete: ' + name)

    # Locate the actual completed per-suite records from this run, never newest
    # directory guesses or copied historical results.
    suites = []
    for item in json_objects((BUILD / 'regressions/01.stdout').read_text()):
        value = item.get('results') or item.get('records')
        if not isinstance(value, str):
            continue
        source = Path(value).resolve()
        require(ROOT / '.build' in source.parents, 'Suite record outside .build')
        directory = source.parent if source.is_file() else source
        if directory not in suites:
            require((directory / 'results.json').is_file(), 'No suite results: ' + str(directory))
            suites.append(directory)
    require(len(suites) == 4, 'Expected four distinct make-check suite records')
    make_groups = []
    legacy_errors = []
    for directory in suites:
        data = read(directory / 'results.json')
        if 'legacy' in data and 'milestone1' in data:
            require(data.get('policy_satisfied') and data['legacy']['known_historical_errors'] == 3,
                    'Historical gap classification changed')
            passed = data['legacy']['outcomes'].get('passed', 0) + data['milestone1']['outcomes'].get('passed', 0)
            errors = data['legacy']['outcomes'].get('error', 0)
            for suite in data['suites']:
                for test in suite['result']['tests']:
                    if test['outcome'] != 'passed':
                        require(test['outcome'] == 'error' and test['classification'] == 'known_historical_gap',
                                'Unexpected original test outcome')
                        legacy_errors.append(test)
            require(errors == len(legacy_errors), 'Historical errors not individually explained')
        else:
            require(data.get('passed'), 'Suite did not pass: ' + str(directory))
            passed, errors = data['tests_run'], 0
            require(all(not group.get('failure_count') and not group.get('error_count')
                        and not group.get('skipped_count') for group in data.get('groups', {}).values()),
                    'Unexpected per-suite outcome')
        make_groups.append({'source': directory.relative_to(ROOT).as_posix(), 'passed': passed, 'errors': errors})

    counts = {
        'make_check': sum(row['passed'] for row in make_groups),
        'app_python': unittest_counts(BUILD / 'regressions/02.stderr'),
        'app_node': node_counts(BUILD / 'regressions/02.stdout'),
        'live_evidence_python': unittest_counts(BUILD / 'regressions/03.stderr'),
        'guidance_data_python': unittest_counts(BUILD / 'new-tests/01.stderr'),
        'portable_runner_python': unittest_counts(BUILD / 'new-tests/02.stderr'),
        'guidance_replay_node': node_counts(BUILD / 'new-tests/03.stdout'),
        'native_focused': sum(unittest_counts(BASE / 'focused-tests' / (row['name'] + '.stderr'))
                              for row in native_commands),
    }
    total = sum(counts.values())
    require(total == 376 and len(legacy_errors) == 3, 'Release count differs; inspect actual logs before packaging')
    require(len(list((BASE / 'native-validation').rglob('trace.jsonl'))) == 7,
            'Expected seven complete original native traces')
    final_integrity = read(BASE / 'final-integrity.json')
    require(final_integrity.get('all_pass') or final_integrity.get('ok') or final_integrity.get('verified'),
            'Original Phase 10 baseline integrity result not verified')

    # Check all original MVP/preservation inventories before adding a new package.
    integrity_run = subprocess.run([sys.executable, '-B', 'docs/phase10_5-evidence/check_integrity.py'],
                                   cwd=ROOT, capture_output=True, text=True)
    require(integrity_run.returncode == 0, 'Prior evidence/package integrity failed')
    integrity = json.loads(integrity_run.stdout)
    require(integrity['verified'], 'Prior integrity result not verified')

    DEST.mkdir(parents=True, exist_ok=False)
    files = []
    def add(source, relative, omit=None):
        require(source.is_file() and not source.is_symlink(), 'Required regular file missing: ' + str(source))
        raw = source.read_bytes()
        row = {'source_path': source.relative_to(ROOT).as_posix(), 'raw_bytes': len(raw), 'raw_sha256': sha(raw)}
        if omit:
            row['omitted_reason'] = omit
        else:
            target = DEST / relative
            packed = gzip.compress(raw, mtime=0) if source.suffix == '.jsonl' else raw
            if source.suffix == '.jsonl':
                target = target.with_name(target.name + '.gz')
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open('xb') as stream:
                stream.write(packed)
            row.update(retained_path=target.relative_to(DEST).as_posix(), retained_sha256=sha(packed),
                       retained_bytes=len(packed), encoding='gzip' if source.suffix == '.jsonl' else 'identity')
        files.append(row)

    def tree(source, prefix):
        for path in sorted(source.rglob('*')):
            if path.is_file():
                omit = 'Host-specific compiled artifact; original source/build metadata and hash retained' if path.suffix in ('.so', '.dylib', '.dll', '.a', '.o') else None
                add(path, Path(prefix) / path.relative_to(source), omit)

    for path in sorted((BUILD / 'native').iterdir()):
        if path.is_file() and path.name != 'baseline.git.tar':
            add(path, Path('native') / path.name)
    add(ROOT / '.build/phase10_5/release-native.stdout', Path('commands/native-wrapper.stdout'))
    add(ROOT / '.build/phase10_5/release-native.stderr', Path('commands/native-wrapper.stderr'))
    tree(BASE / 'native-validation', Path('native/native-validation'))
    tree(BASE / 'focused-tests', Path('native/focused-tests'))
    for name in ('final-integrity.json', 'final-integrity.stdout'):
        add(BASE / name, Path('native') / name)
    for setup_file in sorted((BASE / 'dependencies/setups').glob('*/setup.json')):
        setup = read(setup_file)
        label = setup_file.parent.name
        tree(setup_file.parent, Path('native/preparation') / label)
        assembly = Path(setup['assembly'])
        for name in ('commands.json', 'build-summary.json', 'compiler-version.stdout', 'compiler-version.stderr',
                     'build-yayul.stdout', 'build-yayul.stderr', 'assemble.stderr', 'source-before.json', 'source-after.json'):
            add(assembly / name, Path('native/preparation') / label / 'assembly' / name)
        for key in ('listing', 'symbols', 'rope', 'symtab'):
            add(Path(setup[key]), Path('unused'), 'Reproducible original generated artifact; no duplicate listing or binary copied')
    tree(BUILD / 'regressions', Path('regressions'))
    for index, directory in enumerate(suites, 1):
        tree(directory, Path('regressions/suites') / ('{:02d}'.format(index)))
    tree(BUILD / 'new-tests', Path('new-tests'))
    # Retain the packaging procedure too; this copy is new release evidence.
    add(Path(__file__).resolve(), Path('package_release.py'))
    save(DEST / 'preservation.json', {'command': [sys.executable, '-B', 'docs/phase10_5-evidence/check_integrity.py'],
                                    'exit': integrity_run.returncode, 'result': integrity,
                                    'prior_seals_modified': False})
    summary = {'classification': 'VERIFIED final checks with three known historical missing-evidence errors',
               'passed': total, 'known_historical_errors': len(legacy_errors), 'failed_assertions': 0,
               'unexpected_errors': 0, 'skipped': 0, 'counts': counts, 'make_groups': make_groups,
               'historical_error_details': legacy_errors, 'canonical_raw_trace_matches': native['canonical_trace_matches'],
               'fresh_native_traces': 7, 'powered_descent': 'NOT RUN', 'phase11': 'NOT RUN',
               'ui_data_mode': 'RECORDED AUTHENTIC EXECUTION REPLAY',
               'scope': 'Final precommit checks; historical reports, files, seals and assertions unchanged',
               'base_head': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()}
    save(DEST / 'summary.json', summary)
    (DEST / 'README.md').write_text('''# Final Phase 10 and 10.5 release checks — 2026-10-18

Fresh final checks before commit/push: **376 passed, 3 known historical
missing-evidence errors, 0 failing assertions, 0 unexpected errors, 0 skips**.
Counts are derived from captured per-suite records and actual test logs.
The three errors remain errors; gap-aware command exit zero does not make them
passing tests. Their exact original details are in `summary.json`.

The unchanged original Phase 10 native experiment ran again in a hash-verified
baseline snapshot. All four canonical trace hashes matched; seven complete fresh
native traces (including the Phase 9 controls) are losslessly compressed here.
Command logs retain actual observed paths and bytes. Generated host binaries,
the Git archive and extracted source/build trees are omitted; their source/build
metadata and relevant hashes remain available. No historical logs are recovered
or manufactured by this package.

Reproduce native execution with `python3 -B tools/demo/demo.py reproduce`.
Verify and launch the recorded UI with `make demo-verify` and `make demo`.
See `record.json` and `*.command.json` files for exact executed commands, times
and environment. See the parent Phase 10.5 report for portable prerequisites,
scenario assumptions, source references and actual browser smoke evidence.

Prior Phase 10/10.5 reports, seals and evidence are untouched. `preservation.json`
records their fresh integrity check; this release has its own independent seal.
`checksums.json` covers every release file except itself. `manifest.json` also
records original raw hashes for lossless trace decompression verification.

The UI replays recorded authentic guidance using synthetic mission inputs and a
static state projection. It does not run live pre-ignition guidance. Engine
ignition, thrust response, powered descent and landing remain NOT RUN. **Phase 11
is NOT RUN.** An internal launcher docstring says Python 3.8+; the actual public
launch instructions correctly require Python 3.9+ and govern this release.
''')
    save(DEST / 'manifest.json', {'created_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
                                'scope': 'New final release evidence; no prior inventory updated', 'files': files})
    save(DEST / 'checksums.json', {'scope': 'Every new release file excluding this checksum inventory',
                                  'sha256': {p.relative_to(DEST).as_posix(): sha(p.read_bytes())
                                             for p in sorted(DEST.rglob('*')) if p.is_file()}})
    spec = importlib.util.spec_from_file_location('original_readonly_retainer', ROOT / 'docs/phase10_5-evidence/retain_native.py')
    retainer = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(retainer)
    print(json.dumps({'output': str(DEST), 'summary': summary, 'verification': retainer.verify(DEST)}, indent=2))


if __name__ == '__main__':
    main()
