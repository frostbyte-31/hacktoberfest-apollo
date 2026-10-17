"""Package an actually completed run; never synthesize missing execution output."""
import datetime,gzip,hashlib,json,pathlib,shutil
ROOT=pathlib.Path.cwd()
TARGET=ROOT/'docs/phase7-evidence/runs/2026-10-17-verified-check'
SOURCES={
 'milestone1-tests':'.build/reproducibility/tests/tests-20261017T152734.563537Z',
 'milestone2-tests':'.build/milestone2/tests/20261017T152737Z-e122d7eb',
 'milestone3-tests':'.build/milestone3/tests/20261017T152743Z-dca5477b',
 'phase7-tests':'.build/phase7/tests/20261017T152833Z-14ea9d02',
 'milestone1-demo':'.build/reproducibility/runs/20261017T152748Z-638c4656',
 'milestone2-validation':'.build/milestone2/runs/20261017T152801Z-94abbfd6',
 'milestone3-validation':'.build/milestone3/runs/20261017T152808Z-27ece517',
 'validation':'.build/phase7/runs/20261017T152845Z-71426fa6',
}
def sha(b):return hashlib.sha256(b).hexdigest()
def write(p,d):p.write_text(json.dumps(d,indent=2,sort_keys=True)+'\n')
assert not TARGET.exists()
prior=json.loads((ROOT/'docs/phase7-evidence/prior_hashes.json').read_text())['sha256']
refs={v:(k,'identity') for k,v in prior.items() if k.endswith('.jsonl')}
for k in prior:
 if k.endswith('.jsonl.gz'):
  b=gzip.decompress((ROOT/k).read_bytes());refs.setdefault(sha(b),(k,'gzip'))
for p in (ROOT/SOURCES['validation']/'inputs_source_hashes.json',):
 for n,h in json.loads(p.read_text()).items():assert sha(pathlib.Path(n).read_bytes())==h,n
TARGET.mkdir(parents=True)
record={'packaged_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
 'source_revision':'c10810700d875099d226384a37487376d0cf9460',
 'generated_directories':SOURCES,'identical_trace_references':[],
 'omitted_build_files':[],'lossless_trace_compression':[],'copied_files':[]}
magic=(b'\x7fELF',b'\xcf\xfa\xed\xfe',b'\xfe\xed\xfa\xcf',b'\xca\xfe\xba\xbe')
for label,rel in SOURCES.items():
 src=ROOT/rel
 assert src.is_dir(),src
 for p in sorted(src.rglob('*')):
  if not p.is_file():continue
  assert not p.is_symlink(),p
  sub=p.relative_to(src);dest=TARGET/label/sub
  b=p.read_bytes();entry={'generated_path':str(p.relative_to(ROOT)),
   'retained_path':str(dest.relative_to(TARGET)), 'sha256':sha(b),'bytes':len(b)}
  if 'source' in sub.parts or p.suffix in {'.so','.o','.a','.dylib','.bin','.pyc'} or b[:4] in magic:
   record['omitted_build_files'].append(entry);continue
  if p.suffix=='.jsonl' and entry['sha256'] in refs:
   k,encoding=refs[entry['sha256']]
   entry.update(existing_retained_reference=k,reference_encoding=encoding)
   record['identical_trace_references'].append(entry);continue
  dest.parent.mkdir(parents=True,exist_ok=True)
  if p.suffix=='.jsonl':
   dest=dest.with_suffix('.jsonl.gz')
   with dest.open('wb') as f:
    with gzip.GzipFile(filename='',mode='wb',fileobj=f,mtime=0) as z:z.write(b)
   assert gzip.decompress(dest.read_bytes())==b
   entry.update(retained_path=str(dest.relative_to(TARGET)),gzip_sha256=sha(dest.read_bytes()),gzip_bytes=dest.stat().st_size)
   record['lossless_trace_compression'].append(entry)
  else:
   dest.write_bytes(b);record['copied_files'].append(entry)
for p in sorted((ROOT/'.build/phase7/final-check').iterdir()):
 assert p.is_file()
 shutil.copyfile(p,TARGET/p.name)
shutil.copyfile(__file__,TARGET/'retention-script.py')
write(TARGET/'retention.json',record)
print(json.dumps({k:len(record[k]) for k in ['identical_trace_references','omitted_build_files','lossless_trace_compression','copied_files']}))
print(TARGET)
