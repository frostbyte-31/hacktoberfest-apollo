import test from 'node:test';
import assert from 'node:assert/strict';
import { canPilot, heldDirection, liveSample, LiveClient } from '../dist/live.mjs';

const execution={modreg:0,imodes30:15889,imodes33:15360,dapbools:8910,failreg:[0,0,0]};
const ready=()=>({status:'ready',sessionId:'unit-session',frame:{ready:true,execution}});
const flush=()=>new Promise(resolve=>setImmediate(resolve));
function client(){const c=new LiveClient(()=>{},()=>{});c.latest=ready();c.token='unit-token';return c;}

test('independent directions combine and opposing same-axis controls cancel',()=>{
  assert.deepEqual(heldDirection(new Set(['yaw-','pitch+'])),{yaw:-1,pitch:1});
  assert.deepEqual(heldDirection(new Set(['yaw-','yaw+','pitch-'])),{yaw:0,pitch:-1});
});
test('live controls require both server permission and original readiness',()=>{
  assert.equal(canPilot(ready()),true);
  for(const status of ['idle','initializing','stopping','stopped','fault','disconnected'])assert.equal(canPilot({...ready(),status}),false);
  assert.equal(canPilot({...ready(),frame:{ready:true,execution:{...execution,imodes33:execution.imodes33|32}}}),false);
  assert.equal(canPilot({...ready(),frame:{ready:false,execution}}),false);
});
test('physical freeze and subsequent actual CPU counters remain separate',()=>{
  const native={model_cycle:3200000,physical_time:37.5,cycle:3201034,cdu:[31504,1477,32549],execution,
    model:{quaternion:[1,0,0,0],omega:[0,1.324,0],gimbals:[0,0,0],torque_Nm:[0,0,0],alpha_rad_s2:[0,0,0]}};
  const sample=liveSample(native);
  assert.equal(sample.t,37.5);assert.equal(sample.cpuCycle,3201034);assert.equal(sample.cdu[1],1477);
  assert.deepEqual(sample.q,[1,0,0,0]);
  sample.cdu[1]=0;sample.q[0]=0;
  assert.equal(native.cdu[1],1477);assert.equal(native.model.quaternion[0],1);
  assert.equal(liveSample({model:null}),null);
});
test('malformed live telemetry fails instead of creating a substitute state',()=>{
  assert.throws(()=>liveSample({model:{quaternion:[0,0,0,0],omega:[0,0,0],gimbals:[0,0,0]}}),/orientation/);
});
test('separate held sources preserve another axis when one is released',async()=>{
  const c=client(),sent=[];c.api=async(path,body)=>{sent.push(body);return {};};
  try{
    c.hold('yaw+','pointer-1');await flush();c.hold('pitch-','pointer-2');await flush();
    assert.deepEqual({yaw:sent.at(-1).yaw,pitch:sent.at(-1).pitch},{yaw:1,pitch:-1});
    c.lift('pointer-1');await flush();
    assert.deepEqual({yaw:sent.at(-1).yaw,pitch:sent.at(-1).pitch},{yaw:0,pitch:-1});
    c.lift('pointer-2');await flush();
    assert.equal(sent.at(-1).yaw,0);assert.equal(sent.at(-1).pitch,0);
    const count=sent.length;c.lift('pointer-2');await flush();assert.equal(sent.length,count);
  }finally{clearInterval(c.heartbeat);}
});
test('neutral release can overtake an in-flight deflection with a newer sequence',async()=>{
  const c=client(),sent=[];let finish;
  c.api=(path,body)=>{sent.push(body);return sent.length===1?new Promise(resolve=>{finish=resolve;}):Promise.resolve({});};
  try{
    c.hold('yaw-','key-A');c.release(true);await flush();
    assert.equal(sent.length,2);assert.equal(sent[1].yaw,0);assert.equal(sent[1].pitch,0);
    assert.ok(sent[1].sequence>sent[0].sequence);finish({});await flush();assert.equal(c.pendingInput,0);
  }finally{clearInterval(c.heartbeat);}
});
test('connection loss releases controls and marks retained telemetry stale',async()=>{
  const c=client();c.held.add('yaw+');c.api=async()=>{throw new Error('offline');};
  try{await c.poll();assert.equal(c.latest.status,'disconnected');assert.equal(c.held.size,0);assert.equal(canPilot(c.latest),false);}
  finally{clearInterval(c.heartbeat);}
});
test('inputs are not emitted before native startup is ready',async()=>{
  const c=client();let calls=0;c.api=async()=>{calls++;};c.latest.status='initializing';
  try{c.hold('pitch+','key-W');await flush();assert.equal(calls,0);assert.equal(c.held.size,0);}
  finally{clearInterval(c.heartbeat);}
});
