// Cycle-locked original Comanche DSKY I/O comparison against retained yaAGC.wasm.
// No flight RAM writes, browser scheduling or host socket transport are used.
import fs from 'node:fs';
import crypto from 'node:crypto';
const [nativePath, wasmPath, ropePath, outputPath] = process.argv.slice(2);
if (!outputPath) throw new Error('Usage: node compare_wasm.mjs native.jsonl yaAGC.wasm Comanche055.bin output.json');
const rows = fs.readFileSync(nativePath, 'utf8').trim().split('\n').map(JSON.parse);
const inputs = rows.filter(row => row.ev === 'input');
const expected = rows.filter(row => row.ev === 'output').map(row => [row.cycle, row.channel, row.value]);
const end = Math.max(...rows.map(row => row.afterCycle ?? row.cycle ?? row.consumedAtCycle ?? 0));
// CmOrLm is not exported by the retained WASM module. Its only use in this
// pinned core is the LM RHC channel013/0600 side effect. Reject this comparison
// if that personality-specific path is present instead of claiming it matched.
if (expected.some(([, channel, value]) => channel === 0o13 && (value & 0o600) === 0o600))
  throw new Error('This schedule exercises a CM/LM-specific path unavailable in the retained WASM exports');
const memory = new WebAssembly.Memory({initial: 3, maximum: 4, shared: true});
const wasm = fs.readFileSync(wasmPath);
const rope = fs.readFileSync(ropePath);
const sha = bytes => crypto.createHash('sha256').update(bytes).digest('hex');
if (sha(wasm) !== '5409ecf3000493db731b8143a78855470688f058c5cb8460dff5e848aae00759')
  throw new Error('Retained pinned WASM artifact differs');
if (sha(rope) !== '2ba31de9291cd10fb351a64d261bae8514a1cb75b4651bfa6a135dfa821a2d79')
  throw new Error('Original Comanche055 rope differs');
const wasiCalls = {};
const wasi = new Proxy({}, {get: (_, name) => (...args) => {
  wasiCalls[name] = (wasiCalls[name] ?? 0) + 1;
  if (name === 'proc_exit') throw new Error(`Unexpected WASI exit ${args[0]}`);
  return 0;
}});
const {instance} = await WebAssembly.instantiate(wasm, {env: {memory}, wasi_snapshot_preview1: wasi});
const x = instance.exports;
x.cpu_reset();
const ptr = x.malloc(rope.length);
new Uint8Array(memory.buffer, ptr, rope.length).set(rope);
x.set_fixed(ptr);
x.free(ptr);
let next = 0;
const actual = [];
for (let cycle = 0; cycle < end; cycle++) {
  while (next < inputs.length && inputs[next].queuedAtCycle === cycle) {
    const row = inputs[next++];
    if (x.packet_write(row.channel, row.value) <= 0) throw new Error(`WASM rejected packet at ${cycle}`);
  }
  x.cpu_step(1);
  for (let word; (word = x.packet_read()); ) actual.push([cycle + 1, word >>> 16, word & 32767]);
}
if (next !== inputs.length) throw new Error('Not all real native inputs were replayed');
if (JSON.stringify(actual) !== JSON.stringify(expected)) {
  const index = actual.findIndex((row, i) => JSON.stringify(row) !== JSON.stringify(expected[i]));
  throw new Error(`Cycle-locked native/WASM mismatch at output ${index}: ${JSON.stringify({native: expected[index], wasm: actual[index]})}`);
}
const report = {
  status: 'VERIFIED', cpuCycles: end, inputPackets: inputs.length, outputPackets: actual.length,
  exactCycleChannelValueIdentity: true, wasmSha256: sha(wasm), ropeSha256: sha(rope),
  packetTupleSha256: sha(JSON.stringify(actual)), wasiCalls,
  scope: 'Original Comanche DSKY/PRO subset only; native and retained WASM use the same pinned ringbuffer core. The retained WASM exports lack CM personality selection; no personality-specific RHC path is exercised. No vehicle, IMU, optics or flight-state fidelity is inferred.'
};
fs.writeFileSync(outputPath, JSON.stringify(report, null, 2) + '\n');
console.log(JSON.stringify(report, null, 2));
