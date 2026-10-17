#!/usr/bin/env python3
"""Read-only search for exact historical log bytes; never creates old logs."""
import argparse
import datetime
import gzip
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tarfile
sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def investigate(output):
    output.mkdir(parents=True, exist_ok=False)
    inventory_path = ROOT/'docs/milestone1-evidence/missing-historical.json'
    inventory = json.loads(inventory_path.read_text())
    expected = {record['expected_sha256']: record['path'] for record in inventory['entries']}
    commands = []

    def command(argv):
        result = subprocess.run(argv, cwd=ROOT, capture_output=True)
        row = {'argv': argv, 'exit': result.returncode,
               'stdout_sha256': digest(result.stdout), 'stderr': result.stderr.decode(errors='replace')}
        commands.append(row)
        return result

    paths = [entry['path'] for entry in inventory['entries']]
    history = command(['git', 'log', '--all', '--format=%H', '--', *paths])
    (output/'path-history.stdout').write_bytes(history.stdout)
    fsck = command(['git', 'fsck', '--full', '--no-reflogs', '--unreachable'])
    (output/'fsck.stdout').write_bytes(fsck.stdout)
    objects = command(['git', 'cat-file', '--batch-all-objects', '--batch-check=%(objectname) %(objecttype) %(objectsize)'])
    (output/'object-inventory.stdout').write_bytes(objects.stdout)
    if history.returncode or fsck.returncode or objects.returncode:
        raise ValueError('Git inspection failed; preserve actual command outputs')
    # Inspect reachable AND unreachable local blobs. The original SHA-256
    # inventory is independent of Git's SHA-1 object identifiers.
    blobs = [line.split()[0] for line in objects.stdout.splitlines() if line.split()[1] == b'blob']
    process = subprocess.Popen(['git', 'cat-file', '--batch'], cwd=ROOT, stdin=subprocess.PIPE, stdout=subprocess.PIPE)
    found = []
    git_bytes = 0
    for oid in blobs:
        process.stdin.write(oid+b'\n')
        process.stdin.flush()
        header = process.stdout.readline().split()
        size = int(header[2])
        raw = process.stdout.read(size)
        if len(raw) != size or process.stdout.read(1) != b'\n':
            raise ValueError('Incomplete Git object stream')
        git_bytes += size
        sha = digest(raw)
        if sha in expected:
            found.append({'expected_path': expected[sha], 'sha256': sha, 'git_blob': oid.decode()})
    process.stdin.close()
    process.stdout.close()
    if process.wait():
        raise ValueError('Git object stream exited unsuccessfully')
    local_files, local_bytes = 0, 0
    for directory in (ROOT/'docs', ROOT/'.build'):
        if not directory.is_dir():
            continue
        for path in directory.rglob('*'):
            if not path.is_file() or path.is_symlink() or output in path.parents:
                continue
            # Compiler/host logs and compressed retained execution text, not
            # unrelated executables, source archives, or private filesystem.
            if path.suffix not in ('.log', '.txt', '.stdout', '.stderr', '.gz'):
                continue
            if path.name.endswith(('.tar.gz', '.tgz')):
                continue
            raw = path.read_bytes()
            if path.suffix == '.gz':
                try:
                    raw = gzip.decompress(raw)
                except (OSError, EOFError):
                    continue
            local_files += 1
            local_bytes += len(raw)
            sha = digest(raw)
            if sha in expected:
                found.append({'expected_path': expected[sha], 'sha256': sha, 'local_path': str(path.relative_to(ROOT))})
    archives, archive_members = [], 0
    for path in (ROOT/'docs').rglob('*.tar.gz'):
        row = {'path': str(path.relative_to(ROOT)), 'sha256': digest(path.read_bytes()), 'regular_members_checked': 0}
        try:
            with tarfile.open(path, 'r:gz') as archive:
                for member in archive:
                    if not member.isfile():
                        continue
                    raw = archive.extractfile(member).read()
                    archive_members += 1
                    row['regular_members_checked'] += 1
                    sha = digest(raw)
                    if sha in expected:
                        found.append({'expected_path': expected[sha], 'sha256': sha,
                                      'archive': str(path.relative_to(ROOT)), 'member': member.name})
        except tarfile.TarError as error:
            row['archive_error'] = repr(error)
        archives.append(row)
    previous = json.loads((ROOT/'docs/phase10-evidence/test-results.json').read_text())
    report = {'utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
              'classification': 'VERIFIED exact local matching bytes found' if found else 'UNRESOLVED historical provenance; no exact local copies found',
              'inventory_path': str(inventory_path.relative_to(ROOT)), 'inventory_sha256': digest(inventory_path.read_bytes()),
              'missing_inventory_count': len(paths), 'currently_missing': [name for name in paths if not (ROOT/name).exists()],
              'original_three_errors': previous['historical_errors'], 'path_history_commits': history.stdout.decode().splitlines(),
              'git_blobs_checked': len(blobs), 'git_blob_bytes_checked': git_bytes,
              'workspace_log_candidates_checked': local_files, 'workspace_log_bytes_checked': local_bytes,
              'retained_source_archives': archives, 'archive_regular_members_checked': archive_members,
              'exact_matches': found, 'commands': commands,
              'interpretation': 'Search covers available local Git objects and docs/.build log-like files. It does not prove absence from an external owner backup. New compiler logs cannot be relabeled historical logs. No missing file, placeholder, original test or old inventory was changed.'}
    (output/'report.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps({key: report[key] for key in ('classification', 'missing_inventory_count', 'git_blobs_checked', 'workspace_log_candidates_checked', 'exact_matches')}, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    investigate(args.output.resolve())
