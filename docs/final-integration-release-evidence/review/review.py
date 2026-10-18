"""Read-only release structure checks; emit findings only beside this script."""
import gzip
import hashlib
import json
from pathlib import Path
import re
import subprocess
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
EVIDENCE = ROOT / 'docs/final-integration-evidence'


def sha(path):
    value = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1048576), b''):
            value.update(block)
    return value.hexdigest()


def git(root, *args):
    return subprocess.check_output(['git', *args], cwd=root)


def write(name, value):
    (HERE/name).write_text(json.dumps(value, indent=2)+'\n')


def main():
    utc = datetime.now(timezone.utc).isoformat()
    seal_path = EVIDENCE/'checksums.json'
    seal = json.loads(seal_path.read_text())
    entries = seal['sha256']
    bad, unsafe = [], []
    for name, expected in entries.items():
        path = ROOT/name
        if Path(name).is_absolute() or '..' in Path(name).parts or path.is_symlink():
            unsafe.append(name)
        actual = sha(path) if path.is_file() and not path.is_symlink() else None
        if actual != expected:
            bad.append(name)
    result = {'utc': utc, 'manifestSha256': sha(seal_path),
              'expectedCount': 736, 'entriesVerified': len(entries),
              'mismatchedOrMissingPaths': bad, 'unsafePaths': unsafe,
              'verified': len(entries) == 736 and not bad and not unsafe}
    write('manifest-verification.json', result)

    before = json.loads((EVIDENCE/'preservation-before.json').read_text())['frontend']
    frontend = Path(before['root'])
    names = set(git(frontend, 'ls-files', '--cached', '--others', '--exclude-standard', '-z').decode().split('\0'))-{''}
    names = {name for name in names if (frontend/name).is_file() and not (frontend/name).is_symlink()}
    expected_names = set(before['sha256'])
    changed = [name for name, value in before['sha256'].items()
               if not (frontend/name).is_file() or (frontend/name).is_symlink()
               or sha(frontend/name) != value]
    current_git = {'branch': git(frontend, 'branch', '--show-current').decode().strip(),
                   'head': git(frontend, 'rev-parse', 'HEAD').decode().strip(),
                   'status': git(frontend, 'status', '--porcelain').decode().strip()}
    same_git = {key: current_git[key] == before[key].strip() for key in current_git}
    copied = json.loads((EVIDENCE/'frontend-integration-copy.json').read_text())['files']
    changed_copy = [item['path'] for item in copied if sha(ROOT/item['path']) != item['sha256']]
    reviewed_copy_changes = {}
    if 'frontend/tsconfig.json' in changed_copy:
        old_config = json.loads((frontend/'frontend/tsconfig.json').read_text())
        new_config = json.loads((ROOT/'frontend/tsconfig.json').read_text())
        added_types = ['dist/mission-live-types.d.ts', 'dist/mission-live-provider.mjs']
        options_unchanged = {k: v for k, v in old_config.items() if k != 'files'} == {k: v for k, v in new_config.items() if k != 'files'}
        if options_unchanged and new_config['files'] == old_config['files']+added_types:
            reviewed_copy_changes['frontend/tsconfig.json'] = {
                'reason': 'Intentional final-integration extension: also check the new live-domain types/provider.',
                'addedCompilerFiles': added_types, 'compilerOptionsUnchanged': True,
                'originalWorktreeUnchanged': True,
                'currentBytesIncludedIn736EntrySeal': 'frontend/tsconfig.json' in entries}
    unexpected_copy_changes = sorted(set(changed_copy)-set(reviewed_copy_changes))
    base_comparisons = {}
    for item in copied:
        if item['kind'] == 'modified':
            name = item['path']
            old_backend = git(ROOT, 'show', seal['baseRevision']+':'+name)
            old_frontend = git(frontend, 'show', before['head']+':'+name)
            base_comparisons[name] = old_backend == old_frontend
    preservation = {'utc': utc, 'worktree': str(frontend), 'expectedCount': 5607,
                    'actualInventoryCount': len(names), 'fingerprintsChecked': len(before['sha256']),
                    'changedPaths': changed, 'addedInventoryPaths': sorted(names-expected_names),
                    'missingInventoryPaths': sorted(expected_names-names),
                    'branch': current_git['branch'], 'head': current_git['head'],
                    'gitStateMatches': same_git,
                    'gitStatusSha256': hashlib.sha256(current_git['status'].encode()).hexdigest(),
                    'copiedPathsChecked': len(copied), 'copiedPathsChanged': changed_copy,
                    'reviewedIntegrationCopyChanges': reviewed_copy_changes,
                    'unexpectedIntegrationCopyChanges': unexpected_copy_changes,
                    'modifiedTrackedFrontendBasesAgree': base_comparisons}
    preservation['originalWorktreeVerified'] = (len(names) == 5607 and not changed
                                                and names == expected_names and all(same_git.values()))
    preservation['verified'] = (preservation['originalWorktreeVerified']
                                and not unexpected_copy_changes and all(base_comparisons.values()))
    write('frontend-preservation.json', preservation)

    patterns = {
        'private-key-header': re.compile(rb'-----BEGIN (?:RSA |EC |DSA |OPENSSH |ENCRYPTED )?PRIVATE KEY-----'),
        'aws-access-id': re.compile(rb'\bAKIA[0-9A-Z]{16}\b'),
        'github-token': re.compile(rb'\b(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,})\b'),
        'provider-secret-token': re.compile(rb'\bsk-(?:proj-|ant-)?[A-Za-z0-9_-]{24,}\b'),
    }
    pending_tracked = git(ROOT, 'diff', '--name-only', '--no-renames', seal['baseRevision'], '-z').decode().split('\0')
    pending_new = git(ROOT, 'ls-files', '--others', '--exclude-standard', '-z').decode().split('\0')
    artifact_names = sorted((set(entries)|set(pending_tracked)|set(pending_new))-{''})
    findings, suspicious_names, executables, sizes = [], [], [], []
    for name in artifact_names:
        path = ROOT/name
        if not path.is_file():
            continue
        size = path.stat().st_size
        sizes.append({'path': name, 'bytes': size})
        if path.name in ('.env', 'credentials', 'id_rsa', 'id_ed25519') or path.suffix.lower() in ('.pem', '.p12', '.pfx', '.key', '.pyc') or '__pycache__' in path.parts:
            suspicious_names.append(name)
        with path.open('rb') as stream:
            magic = stream.read(4)
        if magic in (b'\x7fELF', b'\xcf\xfa\xed\xfe', b'\xfe\xed\xfa\xcf', b'\xfe\xed\xfa\xce', b'\xca\xfe\xba\xbe'):
            executables.append(name)
        counts = {key: 0 for key in patterns}
        opener = gzip.open if path.suffix == '.gz' else open
        tail = b''
        with opener(path, 'rb') as stream:
            for block in iter(lambda: stream.read(1048576), b''):
                data = tail+block
                for label, pattern in patterns.items():
                    counts[label] += len(pattern.findall(data))
                tail = data[-512:]
        for label, count in counts.items():
            if count:
                findings.append({'path': name, 'pattern': label, 'count': count})
    ignored = subprocess.run(['git', 'check-ignore', '--stdin', '-z'], input=('\0'.join(artifact_names)+'\0').encode(), cwd=ROOT, capture_output=True)
    ignored_paths = [p for p in ignored.stdout.decode().split('\0') if p]
    artifact = {'utc': utc, 'scope': '736 sealed files plus current pending release receipts and self manifest',
                'filesScanned': len(sizes), 'totalBytes': sum(x['bytes'] for x in sizes),
                'largestFiles': sorted(sizes, key=lambda x: x['bytes'], reverse=True)[:12],
                'filesAtLeast50MiB': [x for x in sizes if x['bytes'] >= 50*1024**2],
                'filesAtLeast100MiB': [x for x in sizes if x['bytes'] >= 100*1024**2],
                'suspiciousFilenames': suspicious_names, 'compiledExecutableMagic': executables,
                'credentialPatternFindings': findings, 'ignoredManifestPaths': ignored_paths,
                'limitations': ['Heuristic structural scan, not proof that every possible secret format is absent.',
                               'Only filenames, pattern identifiers and counts are reported; matched values are never printed.',
                               'Gzip evidence was inspected after decompression; original bytes were not modified.']}
    write('artifact-review.json', artifact)
    print(json.dumps({'manifestVerified': result['verified'], 'manifestEntries': len(entries),
                      'frontendPreserved': preservation['verified'], 'frontendFiles': len(names),
                      'copyFiles': len(copied), 'credentialPatternFindings': len(findings),
                      'suspiciousFilenames': len(suspicious_names), 'compiledExecutables': len(executables),
                      'filesAtLeast50MiB': len(artifact['filesAtLeast50MiB']),
                      'ignoredManifestPaths': len(ignored_paths)}, indent=2))
    if not result['verified'] or not preservation['verified']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
