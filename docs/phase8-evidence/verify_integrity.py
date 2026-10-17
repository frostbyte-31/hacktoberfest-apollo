#!/usr/bin/env python3
"""GPL-2.0-or-later. Check the Phase 8 seal and pre-existing evidence bytes."""
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]

def main():
    results={}
    for label,path in [('prior',HERE/'prior_hashes.json'),('phase8',HERE/'sha256.json')]:
        hashes=json.loads(path.read_text());mismatches=[]
        for name,expected in hashes.items():
            target=ROOT/name
            if not target.is_file() or hashlib.sha256(target.read_bytes()).hexdigest()!=expected:
                mismatches.append(name)
        results[label]={'checked':len(hashes),'mismatches':mismatches,'all_pass':not mismatches}
    print(json.dumps(results,indent=2))
    if not all(row['all_pass'] for row in results.values()):raise SystemExit(1)

if __name__=='__main__':main()
