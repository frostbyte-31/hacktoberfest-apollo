// Test harness only; supports Node and a temporary isolated browser page.
export async function runCycles(wasm, rope, schedule) {
  const memory = new WebAssembly.Memory({ initial: 3, maximum: 4, shared: true });
  const imports = WebAssembly.Module.imports(await WebAssembly.compile(wasm));
  const wasiCalls = {};
  const wasi = new Proxy({}, { get: (_, name) => (...args) => {
    wasiCalls[name] = (wasiCalls[name] || 0) + 1;
    if(name === 'proc_exit') throw new Error(`WASI proc_exit ${args[0]}`);
    return 0;
  }});
  const {instance} = await WebAssembly.instantiate(wasm, {env:{memory}, wasi_snapshot_preview1:wasi});
  const x=instance.exports;
  x.cpu_reset();
  const p=x.malloc(rope.length); new Uint8Array(memory.buffer,p,rope.length).set(rope); x.set_fixed(p); x.free(p);
  const ram = new Uint16Array(memory.buffer,x.get_erasable_ptr(),2048);
  const lines=schedule.trim().split('\n'); const end=Number(lines.shift());
  const inputs=lines.map(l=>l.trim().split(/\s+/).map(Number)); let next=0;
  let hash=2166136261; const out=[];
  const mix=(h,w)=>Math.imul((Math.imul(h^(w&255),16777619)^(w>>>8)),16777619)>>>0;
  for(let i=0;i<end;i++) {
    if(next<inputs.length && i===inputs[next][0]) {
      const [,ch,val]=inputs[next++]; const accepted=x.packet_write(ch,val);
      out.push(JSON.stringify({ev:'input',cycle:i,ch,val,accepted}));
      if(accepted<=0) throw new Error('input ringbuffer rejected packet');
    }
    x.cpu_step(1);
    for(let j=0;j<8;j++) hash=mix(hash,ram[j]);
    for(let v;(v=x.packet_read());) out.push(JSON.stringify({ev:'output',cycle:i+1,ch:v>>>16,val:v&32767}));
    if((i+1)%10000===0 || i+1===end) {
      let ramHash=2166136261; for(const w of ram) ramHash=mix(ramHash,w);
      out.push(JSON.stringify({ev:'trace',cycle:i+1,registerHash:hash,ramHash,z:ram[5],fb:ram[4],eb:ram[3]}));
    }
  }
  return {transcript:out.join('\n')+'\n',imports,wasiCalls,cycles:end};
}
if(typeof process!=='undefined' && process.versions?.node) {
  const fs=await import('node:fs'); const [wasm,rope,schedule,out]=process.argv.slice(2);
  const r=await runCycles(fs.readFileSync(wasm),fs.readFileSync(rope),fs.readFileSync(schedule,'utf8'));
  fs.writeFileSync(out,r.transcript);
  console.log(JSON.stringify({cycles:r.cycles,imports:r.imports,wasiCalls:r.wasiCalls}));
}