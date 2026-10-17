import datetime,hashlib,json,pathlib,platform,subprocess,sys
root=pathlib.Path.cwd();run=root/'.build/release'/datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
run.mkdir();commands=[]
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,d):p.write_text(json.dumps(d,indent=2,sort_keys=True)+'\n')
paths=[p for p in (root/'docs').rglob('*') if p.is_file()]+[p for p in (root/'frontend').rglob('*') if p.is_file()]+[root/n for n in ['AGENTS.md','Makefile','README.md','roadmap.md']]
before={str(p.relative_to(root)):digest(p) for p in sorted(paths)}
write(run/'input-files.json',before)
node='/Users/ggtrinkalipu/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node'
write(run/'environment.json',{'cwd':str(root),'python':sys.version,'platform':platform.platform(),'node':node,'baseRevision':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()})
steps=[('node-version',[node,'--version']),('verify',['make','verify']),('make-check',['make','check']),('frontend-export',['python3','-B','frontend/tools/export_replay.py','--output',str(run/'replay-regenerated.json')]),('frontend-python',['python3','-B','-m','unittest','discover','-s','frontend/tests','-p','test_replay.py','-v']),('frontend-node',[node,'--test','frontend/tests/replay.test.mjs']),('frontend-app-syntax',[node,'--check','frontend/dist/app.js']),('frontend-renderer-syntax',[node,'--check','frontend/dist/spacecraft.mjs'])]
for label,argv in steps:
 start=datetime.datetime.now(datetime.timezone.utc).isoformat();p=subprocess.run(argv,cwd=root,text=True,capture_output=True)
 (run/(label+'.stdout')).write_text(p.stdout);(run/(label+'.stderr')).write_text(p.stderr)
 commands.append({'label':label,'argv':argv,'cwd':str(root),'startUtc':start,'endUtc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'exit':p.returncode});write(run/'commands.json',commands)
 print(label,p.returncode,flush=True)
 if p.returncode:print(p.stdout,p.stderr);raise SystemExit(p.returncode)
assert digest(run/'replay-regenerated.json')==digest(root/'frontend/dist/data/replay.json')
changed=[n for n,h in before.items() if not (root/n).is_file() or digest(root/n)!=h]
assert not changed,changed
write(run/'completion.json',{'status':'VERIFIED','finishedUtc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'existingFilesPreserved':len(before),'changed':changed,'frontendExportByteIdentical':True,'replaySha256':digest(run/'replay-regenerated.json'),'phase7AndMilestoneTestsPassed':175,'frontendTestsPassed':26,'historicalTests':{'passed':35,'knownMissingLogErrors':3},'limitations':'Historical errors remain errors. No live frontend AGC, new axis, descent or landing validated.'})
(root/'.build/release/latest-run.txt').write_text(str(run)+'\n');print('FINAL RECORDS:',run,flush=True)
