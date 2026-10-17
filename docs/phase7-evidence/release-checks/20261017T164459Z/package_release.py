"""Retain actual final-check artifacts without altering earlier evidence."""
import datetime,gzip,hashlib,io,json,pathlib,shutil,subprocess
ROOT=pathlib.Path.cwd();RUN=ROOT/'.build/release/20261017T164459Z';TARGET=ROOT/'docs/phase7-evidence/release-checks/20261017T164459Z'
PHASE7='903660d2de58431a6f485001226231ee981b0854'
SOURCES={
 'checks':'.build/release/20261017T164459Z',
 'tests/milestone1':'.build/reproducibility/tests/tests-20261017T164459.977867Z',
 'tests/milestone2':'.build/milestone2/tests/20261017T164501Z-0792c837',
 'tests/milestone3':'.build/milestone3/tests/20261017T164504Z-55144cef',
 'tests/phase7':'.build/phase7/tests/20261017T164531Z-fe528a23',
 'native/phase6-reproduction':'.build/reproducibility/runs/20261017T164507Z-cd2e4c91',
 'native/milestone2':'.build/milestone2/runs/20261017T164513Z-49738120',
 'native/milestone3':'.build/milestone3/runs/20261017T164517Z-2e9f6a8f',
 'native/phase7':'.build/phase7/runs/20261017T164537Z-5214f47d',
 'browser-original/verification':'.build/frontend/verification',
 'browser-original/screenshots':'.build/frontend/screenshots',
}
def sha(b):return hashlib.sha256(b).hexdigest()
def write(p,d):p.write_text(json.dumps(d,indent=2,sort_keys=True)+'\n')
assert not TARGET.exists()
manifest=json.loads((ROOT/'docs/phase7-evidence/package-manifest.json').read_text())['files']
objects=[]
for name in manifest:
 oid=subprocess.check_output(['git','rev-parse',PHASE7+':'+name],text=True).strip();objects.append((name,oid))
raw=subprocess.run(['git','cat-file','--batch'],input=''.join(oid+'\n' for name,oid in objects).encode(),capture_output=True,check=True).stdout;s=io.BytesIO(raw)
for name,oid in objects:
 n=int(s.readline().split()[2]);b=s.read(n);assert s.read(1)==b'\n';assert sha(b)==manifest[name]['sha256'],name
refs={}
for name in subprocess.check_output(['git','ls-files','docs'],text=True).splitlines():
 p=ROOT/name
 if name.endswith('.jsonl'):refs.setdefault(sha(p.read_bytes()),(name,'identity'))
 if name.endswith('.jsonl.gz'):refs.setdefault(sha(gzip.decompress(p.read_bytes())),(name,'gzip'))
TARGET.mkdir(parents=True)
record={'packagedUtc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'phase7SnapshotCommit':PHASE7,'phase7PackageEntriesVerifiedInGit':len(manifest),'generatedDirectories':SOURCES,'copiedFiles':[],'identicalTraceReferences':[],'losslessTraceCompression':[],'omittedRebuildableFiles':[],'duplicateFrontendData':[]}
expectedData=sha((ROOT/'frontend/dist/data/replay.json').read_bytes())
magic={b'\x7fELF',b'\xcf\xfa\xed\xfe',b'\xfe\xed\xfa\xcf',b'\xca\xfe\xba\xbe'}
for label,relative in SOURCES.items():
 src=ROOT/relative;assert src.is_dir(),src
 for p in sorted(src.rglob('*')):
  assert not p.is_symlink(),p
  if not p.is_file():continue
  sub=p.relative_to(src);dest=TARGET/label/sub;b=p.read_bytes()
  e={'generatedPath':str(p.relative_to(ROOT)),'retainedPath':str(dest.relative_to(TARGET)),'sha256':sha(b),'bytes':len(b)}
  if label=='checks' and p.name in {'replay-regenerated.json','http-replay.json'}:
   assert e['sha256']==expectedData
   e['existingRetainedReference']='frontend/dist/data/replay.json';record['duplicateFrontendData'].append(e);continue
  if 'source' in sub.parts or p.suffix in {'.so','.o','.a','.dylib','.bin','.pyc'} or b[:4] in magic:
   record['omittedRebuildableFiles'].append(e);continue
  if p.suffix=='.jsonl' and e['sha256'] in refs:
   name,encoding=refs[e['sha256']];e.update(existingRetainedReference=name,referenceEncoding=encoding);record['identicalTraceReferences'].append(e);continue
  dest.parent.mkdir(parents=True,exist_ok=True)
  if p.suffix=='.jsonl':
   dest=dest.with_suffix('.jsonl.gz')
   with dest.open('wb') as f:
    with gzip.GzipFile(filename='',mode='wb',fileobj=f,mtime=0) as z:z.write(b)
   assert gzip.decompress(dest.read_bytes())==b
   e.update(retainedPath=str(dest.relative_to(TARGET)),gzipSha256=sha(dest.read_bytes()),gzipBytes=dest.stat().st_size)
   record['losslessTraceCompression'].append(e)
  else:dest.write_bytes(b);record['copiedFiles'].append(e)
for name in ['final_checks.py','package_release.py']:
 shutil.copyfile(ROOT/'.build/release'/name,TARGET/name)
shutil.copyfile(ROOT/'.build/frontend/preservation.json',TARGET/'browser-original/preservation-before-frontend.json')
write(TARGET/'retention.json',record)
print(json.dumps({k:len(record[k]) for k in ['copiedFiles','identicalTraceReferences','losslessTraceCompression','omittedRebuildableFiles','duplicateFrontendData']},indent=2))
print(TARGET)
