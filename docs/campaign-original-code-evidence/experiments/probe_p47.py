#!/usr/bin/env python3
"""Retain a negative original-P47 probe after a real completed P52 fixture.

Validation harness only. It sends the same public keys/manual instrument inputs
as the player; no host memory writes, invented displays or flight controls.
Use a new output directory. Earlier Apollo/emulator/evidence files stay intact.
"""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from backend.cmc_alignment import _AlignmentComputer, prepare_alignment_assets
from backend.cmc_native import DskyDecoder


def run(out, assets=None, terminate_integration=False):
    out = Path(out).resolve()
    out.mkdir(parents=True, exist_ok=False)
    if assets is None:
        assets = prepare_alignment_assets(out/'assets')
    computer = _AlignmentComputer(assets, out)
    frames = []

    def observe(label, value=None):
        value = value or computer.snapshot()
        frames.append({'label': label, 'computer': value})
        return value

    def keys(label, text):
        for key in text.split():
            computer.key(key)
        return observe(label, computer.advance(3))

    try:
        observe('fresh-original-p51-setup', computer.boot())
        keys('select-p52', 'VERB 3 7 ENTR 5 2 ENTR')
        keys('refsmmat-option', 'VERB 2 2 ENTR 0 0 0 0 3 ENTR PRO')
        keys('manual-star-selection', 'ENTR')
        keys('identify-menkent', 'VERB 2 1 ENTR 0 0 0 3 0 ENTR PRO')
        observe('mark-menkent', computer.instrument('mark', 'MARK')['computer'])
        keys('review-menkent', 'PRO')
        keys('confirm-menkent', 'PRO')
        keys('identify-nunki', 'VERB 2 1 ENTR 0 0 0 3 7 ENTR PRO')
        # Identical bounded deflections to the documented player's UI route.
        for rate, duration, count in [('HIGH', 1, 5), ('HIGH', .1, 2), ('LOW', 1, 2)]:
            for _ in range(count):
                computer.instrument('optics_slew', {'shaft': 1, 'trunnion': 0,
                                                    'rate': rate, 'seconds': duration})
        observe('mark-nunki', computer.instrument('mark', 'MARK')['computer'])
        keys('review-nunki', 'PRO')
        keys('original-star-fit', 'PRO')
        keys('original-gyro-review', 'PRO')
        keys('approve-gyro-correction', 'PRO')
        observe('applied-gyro-feedback', computer.advance(15))
        aligned = keys('qualified-p52-p00', 'VERB 3 7 ENTR 0 0 ENTR')
        if not aligned['instruments']['alignment']['p52Complete']:
            raise RuntimeError('The prerequisite original P52 did not complete')
        if terminate_integration:
            keys('original-v96-control', 'VERB 9 6 ENTR')
        requested_at = computer.snapshot()['cycle']
        requested = keys('request-original-p47', 'VERB 3 7 ENTR 4 7 ENTR')
        observe('after-ten-cpu-seconds', computer.advance(10))
        n62 = keys('request-n62', 'VERB 1 6 NOUN 6 2 ENTR')
        observe('n62-after-five-cpu-seconds', computer.advance(5))
        alarms = keys('inspect-original-alarm-registers', 'VERB 0 5 NOUN 0 9 ENTR')
        final = keys('recover-to-p00', 'VERB 3 7 ENTR 0 0 ENTR')
    finally:
        computer.trace.close()

    raw = (out/'trace.jsonl').read_bytes()
    decoder = DskyDecoder()
    transient_p47 = []
    p47_n83 = []
    for line in raw.splitlines():
        row = json.loads(line)
        if row.get('ev') != 'output':
            continue
        decoder.apply(row['channel'], row['value'], row['cycle'])
        dsky = decoder.snapshot()
        if row['cycle'] >= requested_at and dsky['PROG'] == '47':
            transient_p47.append(row['cycle'])
            if dsky['VERB'] == '16' and dsky['NOUN'] == '83':
                p47_n83.append(row['cycle'])
    summary = {
        'classification': 'NEGATIVE ORIGINAL EXECUTION PROBE',
        'scope': 'Stationary synthetic CSM instrument fixture; no validated navigation initialization or flight state.',
        'originalSoftware': 'Comanche055', 'provenance': final['provenance'],
        'hostFlightMemoryWrites': False, 'flightExecuted': False,
        'historicalCheckpointLoaded': False,
        'terminateIntegrationControl': terminate_integration,
        'p52QualifiedBeforeP47': aligned['instruments']['alignment']['p52Complete'],
        'requestedAtCycle': requested_at,
        'originalP47RelayObserved': bool(transient_p47),
        'firstP47RelayCycle': min(transient_p47) if transient_p47 else None,
        'lastP47RelayCycle': max(transient_p47) if transient_p47 else None,
        'originalP47N83MonitorObserved': bool(p47_n83),
        'afterRequestDsky': requested['dsky'],
        'n62DskyAfterAbort': n62['dsky'],
        'alarmDsky': alarms['dsky'], 'finalDsky': final['dsky'],
        'p47MonitoringQualified': False,
        'observedFailure': ('Original 01204: negative or zero WAITLIST call.'
                            if '01204' in [alarms['dsky'][name] for name in ('R1', 'R2', 'R3')]
                            else 'Original alarm registers differ; inspect alarmDsky.'),
        'cause': 'Exact initialization cause is unresolved; this fixture supplies no validated CMC navigation state.',
        'interpretation': 'Original P47 was selected transiently but did not sustain its automatic N83 monitor. N62 zeros after abort are not a qualified P47 result.',
        'traceSha256': hashlib.sha256(raw).hexdigest(),
        'rawTraceBytes': len(raw), 'frameCount': len(frames),
    }
    (out/'summary.json').write_text(json.dumps(summary, indent=2)+'\n')
    with gzip.open(out/'frames.json.gz', 'wt') as stream:
        json.dump(frames, stream, separators=(',', ':'))
    with gzip.open(out/'trace.jsonl.gz', 'wb') as stream:
        stream.write(raw)
    (out/'trace.jsonl').unlink()
    return summary


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', required=True, type=Path)
    parser.add_argument('--assets', type=Path)
    parser.add_argument('--terminate-integration', action='store_true')
    args = parser.parse_args()
    result = run(args.out, json.loads(args.assets.read_text()) if args.assets else None,
                 args.terminate_integration)
    print(json.dumps(result, indent=2))
