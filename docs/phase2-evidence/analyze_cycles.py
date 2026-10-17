"""Decode channel 010 and compare complete cycle-indexed test transcripts."""
import json, hashlib, sys
from pathlib import Path
SEG = {0:' ',21:'0',3:'1',25:'2',27:'3',15:'4',30:'5',28:'6',19:'7',29:'8',31:'9'}
ROW = {11:('PROG',0,'PROG',1),10:('VERB',0,'VERB',1),9:('NOUN',0,'NOUN',1),8:(None,0,'R1',0),7:('R1',1,'R1',2),6:('R1',3,'R1',4),5:('R2',0,'R2',1),4:('R2',2,'R2',3),3:('R2',4,'R3',0),2:('R3',1,'R3',2),1:('R3',3,'R3',4)}
def decode(path):
    d={k:list('?'*n) for k,n in [('PROG',2),('VERB',2),('NOUN',2),('R1',5),('R2',5),('R3',5)]}
    last=None; states=[]; trace=0; outputs=0; lamps=[]
    for line in Path(path).read_text().splitlines():
        r=json.loads(line)
        if r['ev']=='trace': trace+=1
        if r['ev']!='output': continue
        outputs+=1
        if r['ch'] in (0o11,0o163): lamps.append(r)
        if r['ch']!=0o10: continue
        v=r['val']; row=(v>>11)&15
        if row not in ROW: continue
        l,li,rr,ri=ROW[row]
        if l:d[l][li]=SEG.get((v>>5)&31,'?')
        d[rr][ri]=SEG.get(v&31,'?')
        snap={k:''.join(chars) for k,chars in d.items()}
        if snap!=last:states.append({'cycle':r['cycle'],'display':snap}); last=snap
    return {'traceCheckpoints':trace,'outputPackets':outputs,'distinctDisplayFrames':len(states),'states':states,'lampChannels':lamps}
if __name__=='__main__':
    a,b=sys.argv[1:3]
    aa=Path(a).read_bytes();bb=Path(b).read_bytes()
    result={'identical':aa==bb,'nativeSHA256':hashlib.sha256(aa).hexdigest(),'otherSHA256':hashlib.sha256(bb).hexdigest(),**decode(a)}
    print(json.dumps(result,indent=2));sys.exit(0 if aa==bb else 1)