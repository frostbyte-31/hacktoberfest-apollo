import argparse,datetime,json,subprocess,sys
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--group',choices=['provider','mission','http'],required=True);p.add_argument('--label',required=True);a=p.parse_args()
patterns={'provider':'test_crew_ai.py','mission':'test_mission_ai.py','http':'test_final_http.py'}
root=Path.cwd();out=root/'.build/crew-ai-checks';cmd=[sys.executable,'-B','-m','unittest','discover','-s','backend/tests','-p',patterns[a.group],'-v']
record={'argv':cmd,'cwd':str(root),'started_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'classification':'Synthetic provider stubs; no real model credentials or remote model requests'}
with (out/(a.label+'.stdout')).open('w') as stdout,(out/(a.label+'.stderr')).open('w') as stderr:
 result=subprocess.run(cmd,stdout=stdout,stderr=stderr)
record.update(exit=result.returncode,ended_utc=datetime.datetime.now(datetime.timezone.utc).isoformat());(out/(a.label+'.command.json')).write_text(json.dumps(record,indent=2)+'\n');print(json.dumps(record,indent=2));raise SystemExit(result.returncode)
