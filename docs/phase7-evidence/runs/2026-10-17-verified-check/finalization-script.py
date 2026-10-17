"""Record final local integrity after the completed experiments; no Git mutation."""
import collections,datetime,gzip,hashlib,importlib.util,json,pathlib,re,shutil,subprocess,sys
sys.dont_write_bytecode=True
ROOT=pathlib.Path.cwd();HERE=ROOT/'docs/phase7-evidence'
now=lambda:datetime.datetime.now(datetime.timezone.utc).isoformat()
def sha(b):return hashlib.sha256(b).hexdigest()
def write(p,d):p.write_text(json.dumps(d,indent=2,sort_keys=True)+'\n')
started=now()
spec=importlib.util.spec_from_file_location('final_phase7_common',HERE/'common.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
preserved=m.verify_prior();assert preserved['ok'],preserved
inputs=json.loads((HERE/'runs/2026-10-17-verified-check/validation/inputs_source_hashes.json').read_text())
for n,h in inputs.items():assert sha(pathlib.Path(n).read_bytes())==h,n
r=HERE/'runs/2026-10-17-verified-check';ret=json.loads((r/'retention.json').read_text())
for kind in ['copied_files','lossless_trace_compression','identical_trace_references']:
 for x in ret[kind]:
  if kind=='identical_trace_references':
   p=ROOT/x['existing_retained_reference'];b=p.read_bytes()
   if x['reference_encoding']=='gzip':b=gzip.decompress(b)
  else:
   p=r/x['retained_path'];b=p.read_bytes()
   if kind=='lossless_trace_compression':
    assert sha(b)==x['gzip_sha256'],p
    b=gzip.decompress(b)
  assert sha(b)==x['sha256'],p
shutil.copyfile(__file__,r/'finalization-script.py')
for p in [HERE/'repository-state.json',HERE/'package-manifest.json']:
 assert not p.exists(),p
 write(p,{})
links=[]
for name in ['docs/PHASE7_MULTIAXIS_VALIDATION.md','docs/phase7-evidence/README.md']:
 p=ROOT/name
 for dest in re.findall(r'\]\(([^)]+)\)',p.read_text()):
  if not dest.startswith(('http:', 'https:', '#')):
   assert (p.parent/dest).exists(),(p,dest);links.append({'document':name,'target':dest})
json_count=gzip_count=0
for p in sorted(HERE.rglob('*')):
 assert not p.is_symlink(),p
 if not p.is_file():continue
 assert p.stat().st_size<100_000_000,p
 assert p.suffix not in {'.pyc','.so','.o','.dylib'},p
 if p.suffix=='.json':json.loads(p.read_text());json_count+=1
 if p.name.endswith('.jsonl.gz'):
  b=gzip.decompress(p.read_bytes())
  for line in b.splitlines():json.loads(line)
  gzip_count+=1
commands=[]
def git(*args):
 argv=['git',*args];s=now();c=subprocess.run(argv,cwd=ROOT,text=True,capture_output=True)
 commands.append({'argv':argv,'start_utc':s,'end_utc':now(),'exit':c.returncode,'stdout':c.stdout,'stderr':c.stderr})
 assert c.returncode==0,commands[-1]
 return c.stdout.rstrip('\n')
branch=git('branch','--show-current');head=git('rev-parse','HEAD')
assert branch=='main' and head=='c10810700d875099d226384a37487376d0cf9460'
git('diff','--check')
status=git('status','--short','--untracked-files=all')
modified=git('diff','--name-only').splitlines();untracked=git('ls-files','--others','--exclude-standard').splitlines()
assert set(modified)=={'Makefile','README.md','roadmap.md'},modified
assert git('diff','--cached','--name-only')==''
state={'captured_utc':now(),'branch':branch,'head':head,'origin':git('remote','get-url','origin'),
 'phase7_commit_created':False,'phase7_pushed':False,'index_clean':True,'working_tree_clean':False,
 'modified_tracked_files':modified,'untracked_files':untracked,
 'authorized_scope':'Phase7 implementation/testing only; no Phase8, Git history mutation or push',
 'commands':commands}
write(HERE/'repository-state.json',state)
write(HERE/'final-integrity.json',{'status':'VERIFIED','started_utc':started,'finished_utc':now(),
 'prior_preservation':preserved,'executed_input_hashes_verified':len(inputs),
 'final_retention_groups_verified':{k:len(ret[k]) for k in ['copied_files','lossless_trace_compression','identical_trace_references']},
 'json_files_parsed_before_this_record':json_count,'gzip_jsonl_files_parsed':gzip_count,
 'report_entrypoint_links_verified':links,'git_diff_check_exit':0,
 'no_symlinks_or_compiled_libraries_or_oversized_files':True,
 'scope':'Packaging integrity; does not replace actual test and native execution records'})
paths=[p for p in HERE.rglob('*') if p.is_file() and p.name!='package-manifest.json']
paths += [ROOT/n for n in ['Makefile','README.md','roadmap.md','docs/PHASE7_MULTIAXIS_VALIDATION.md']]
manifest={str(p.relative_to(ROOT)):{'sha256':sha(p.read_bytes()),'bytes':p.stat().st_size} for p in sorted(paths)}
write(HERE/'package-manifest.json',{'schema':1,'captured_utc':now(),'base_revision':head,
 'scope':'NewPhase7 evidence/report and changed root entrypoints; inventory excludes itself',
 'files':manifest})
for n,info in manifest.items():assert sha((ROOT/n).read_bytes())==info['sha256'],n
print(json.dumps({'status':'VERIFIED','prior_files_preserved':preserved['files_checked'],
 'executed_inputs_unchanged':len(inputs),'package_files':len(manifest),
 'json_files_parsed':json_count,'gzip_jsonl_files_parsed':gzip_count,
 'branch':branch,'head':head,'modified_tracked_files':modified,'untracked_files':len(untracked)},indent=2))
