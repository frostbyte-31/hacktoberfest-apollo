// Phase 1 / WebAssembly evaluation. This runs the upstream yaAGC.wasm target
// (yaAGC/wasm.c, unmodified) on the same rope image, with the same keystroke
// script as m2_dsky_client.py. It logs channel 010 relay words.
// Time is simulated: one cpu_step equals one AGC memory cycle of 11.72 us
// (see the comment in wasm.c), so 85333 steps are about 1 s.
// Usage: node wasm_dsky_harness.mjs yaAGC.wasm MAIN.agc.bin out.jsonl
import fs from "node:fs";
const [wasmPath, ropePath, outPath] = process.argv.slice(2);
const memory = new WebAssembly.Memory({ initial: 3, maximum: 4, shared: true });
const wasi = new Proxy({}, { get: () => () => 0 }); // stub WASI calls; I/O goes via ring buffers
const { instance } = await WebAssembly.instantiate(fs.readFileSync(wasmPath), {
  env: { memory }, wasi_snapshot_preview1: wasi,
});
const x = instance.exports;
const rope = fs.readFileSync(ropePath);
const p = x.malloc(rope.length);
new Uint8Array(memory.buffer, p, rope.length).set(rope);
x.cpu_reset();
x.set_fixed(p);

const KEY = { V: 17, N: 31, E: 28, R: 18, "0": 16 };
for (let d = 1; d <= 9; d++) KEY[String(d)] = d;
const SEG = { 0: " ", 21: "0", 3: "1", 25: "2", 27: "3", 15: "4", 30: "5", 28: "6", 19: "7", 29: "8", 31: "9" };
const ROW = { 11: ["MD1", "MD2"], 10: ["VD1", "VD2"], 9: ["ND1", "ND2"], 8: [null, "R1D1"],
  7: ["R1D2", "R1D3"], 6: ["R1D4", "R1D5"], 5: ["R2D1", "R2D2"], 4: ["R2D3", "R2D4"],
  3: ["R2D5", "R3D1"], 2: ["R3D2", "R3D3"], 1: ["R3D4", "R3D5"] };
const disp = {}; Object.values(ROW).flat().filter(Boolean).forEach((f) => (disp[f] = "?"));
const g = (...k) => k.map((f) => disp[f]).join("");
const snap = () => ({ PROG: g("MD1", "MD2"), VERB: g("VD1", "VD2"), NOUN: g("ND1", "ND2"),
  R1: g("R1D1", "R1D2", "R1D3", "R1D4", "R1D5"), R2: g("R2D1", "R2D2", "R2D3", "R2D4", "R2D5"),
  R3: g("R3D1", "R3D2", "R3D3", "R3D4", "R3D5") });

const out = fs.createWriteStream(outPath);
const STEPS_PER_S = 85333;
let steps = 0;
const emit = (r) => out.write(JSON.stringify({ ...r, t_sim: +(steps / STEPS_PER_S).toFixed(3) }) + "\n");
function run(sec) {
  const n = Math.round(sec * STEPS_PER_S);
  for (let i = 0; i < n; i += 100) {
    x.cpu_step(100); steps += 100;
    for (let v; (v = x.packet_read()); ) {
      const ch = v >>> 16, val = v & 0x7fff;
      const rec = { ev: "rx", ch: "0o" + ch.toString(8), val: "0o" + val.toString(8) };
      if (ch === 0o10) {
        const a = (val >> 11) & 0xf;
        if (ROW[a]) {
          const [l, r] = ROW[a];
          if (l) disp[l] = SEG[(val >> 5) & 31] ?? `<${(val >> 5) & 31}>`;
          disp[r] = SEG[val & 31] ?? `<${val & 31}>`;
        }
        rec.display = snap();
      }
      emit(rec);
    }
  }
}
const keys = (s) => { for (const k of s) { emit({ ev: "tx_key", key: k, val: "0o" + KEY[k].toString(8) }); x.packet_write(0o15, KEY[k]); run(0.4); } };
run(5); keys("V35E"); run(8); keys("R"); keys("V16N36E"); run(6);
emit({ ev: "final", display: snap() });
out.end();
