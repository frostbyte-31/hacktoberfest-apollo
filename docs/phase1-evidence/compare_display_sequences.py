# Compares the ordered sequence of distinct DSKY display states (timing ignored),
# taken from the native (21_) and WebAssembly (31_) transcripts.
import json,sys
def seq(f):
    out=[];last=None
    for l in open(f):
        r=json.loads(l)
        if 'display' in r and r.get('ev')=='rx':
            d=r['display']
            if '?' in ''.join(d.values()): continue   # skip pre-initialised states
            d=json.dumps(d,sort_keys=True)
            if d!=last: out.append(d); last=d
    return out
a,b=seq(sys.argv[1]),seq(sys.argv[2])
# strip the mission-clock-advancing tail (R3 values differ by wall/sim timing)
def key_states(s): return [x for x in s if '"NOUN": "36"' not in x or '88' in x]
print("native distinct states:",len(a)," wasm distinct states:",len(b))
ka,kb=key_states(a),key_states(b)
print("states before clock display: native",len(ka),"wasm",len(kb),"identical:",ka==kb)
for i,(x,y) in enumerate(zip(ka,kb)):
    if x!=y: print("first diff at",i,"\n native",x,"\n wasm  ",y); break
