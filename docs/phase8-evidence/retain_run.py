#!/usr/bin/env python3
"""GPL-2.0-or-later. Losslessly retain one new Phase 8 scratch run."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import shutil

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source',type=Path)
    parser.add_argument('destination',type=Path)
    args=parser.parse_args()
    source,destination=args.source.resolve(),args.destination.resolve()
    destination.mkdir(parents=True,exist_ok=False)
    hashes={};omitted={}
    for path in sorted(source.iterdir()):
        if not path.is_file():raise ValueError('Unexpected nested run directory')
        data=path.read_bytes();sha=hashlib.sha256(data).hexdigest()
        if path.name in ('p63_probe','phase5_probe'):
            omitted[path.name]={'sha256':sha,'reason':'Native binary omitted; corresponding source/build commands retained'}
            continue
        if path.suffix=='.stdout' and len(data)>30000:
            target=destination/(path.name+'.gz')
            target.write_bytes(gzip.compress(data,mtime=0))
            if gzip.decompress(target.read_bytes())!=data:raise RuntimeError('Compression verification failed')
        else:
            target=destination/path.name;shutil.copy2(path,target)
        hashes[path.name]={'retained_name':target.name,'raw_sha256':sha,'raw_bytes':len(data),
                           'retained_sha256':hashlib.sha256(target.read_bytes()).hexdigest()}
    (destination/'retention.json').write_text(json.dumps({'source':str(source),'files':hashes,
        'omitted_binaries':omitted,'compression':'gzip, mtime0, lossless byte comparison performed'},indent=2)+'\n')

if __name__=='__main__':main()
