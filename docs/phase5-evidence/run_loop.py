"""Bounded real-AGC/active-Tcl-model attitude response, GPL-2.0-or-later.

Fixed ~10ms coupling, no real-time sockets; no absolute sensor or flight-state writes.
Each mode starts a fresh CPU process and fresh synthetic LM-7 model.
"""
from pathlib import Path
import ctypes, subprocess, sys, json, re
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]

def main():
    source, library, output, mode = sys.argv[1:]
    lib = ctypes.CDLL(library)
    lib.cpu_reset()
    rope = (ctypes.c_ubyte * 73728).from_buffer_copy((ROOT / 'docs/phase1-evidence/artifacts/MAIN.agc.bin').read_bytes())
    lib.set_fixed(rope)
    lines = (HERE / 'operate_inputs.txt').read_text().splitlines()
    end = int(lines[0]); schedule = [list(map(int, l.split())) for l in lines[1:]]
    if mode == 'negative':
        for row in schedule:
            if row[0] == 2500000: row[2] = 12279  # opposite direction bit4 low; bit3 high
            if row[0] == 2500001: row[2] = 32747  # one's-complement -20
    log = Path(output).open('w')
    stderr = Path(output + '.tcl.stderr').open('w')
    proc = subprocess.Popen(['nix', 'shell', 'nixpkgs#tcl', '-c', 'tclsh', str(HERE / 'plant_server.tcl'), source], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=stderr, text=True, bufsize=1)
    if proc.stdin is None or proc.stdout is None: raise RuntimeError('No plant pipes')
    def emit(row): log.write(json.dumps(row, separators=(',', ':')) + '\n')
    emit({'ev': 'initial', 'mode': mode, 'cycles': end, 'coupling_cpu_calls': 853, 'cycle_seconds': 0.00001172, 'model': 'active upstream LM-7 defaults', 'ram_writes': 0})
    tick = 0; idx = 0; jets = {5: 0, 6: 0}; zero = 0
    while tick < end:
        while idx < len(schedule) and schedule[idx][0] == tick:
            _, ch, value = schedule[idx]; idx += 1
            ok = lib.packet_write(ch, value)
            emit({'ev': 'input', 'cycle': tick, 'channel': ch, 'value': value, 'accepted': ok})
            if ok <= 0: raise RuntimeError('Input rejected')
        count = min(853, end - tick)
        if idx < len(schedule): count = min(count, schedule[idx][0] - tick)
        used = lib.step_chunk(count)
        if used < 0: raise RuntimeError('Output overflow')
        events = []
        for i in range(used):
            word = lib.output_word(i); ch, val = (word >> 16) & 65535, word & 32767
            at = lib.output_cycle(i)
            emit({'ev': 'output', 'cycle': at, 'channel': ch, 'value': val})
            if ch in (5, 6, 10): events.append((at, ch, val))
        # Integrate each actual jet/zeroing latch interval, not a fabricated command.
        intervals = events + [(tick + count, -1, 0)]
        cursor = tick
        for at, ch, val in intervals:
            dt = (at - cursor) * 0.00001172
            if dt > 0:
                proc.stdin.write(f'{dt} {jets[5]} {jets[6]} {zero} {int(mode == "blocked")}\n'); proc.stdin.flush()
                response = proc.stdout.readline().strip()
                if '|' not in response: raise RuntimeError('Plant failed: ' + response)
                state, packets = response.split('|'); state = list(map(float, state.split()))
                for op, address in re.findall(r'(PCDU_FAST|MCDU_FAST|PCDU|MCDU) (\d+)', packets):
                    addr = int(address, 8); code = {'PCDU': 1, 'MCDU': 3, 'PCDU_FAST': 17, 'MCDU_FAST': 19}[op]
                    accepted = 0 if mode == 'feedback_off' else lib.packet_write(128 | addr, code)
                    emit({'ev': 'sensor', 'cycle': tick + count, 'origin_interval_end': at, 'counter': addr, 'code': code, 'delivered': mode != 'feedback_off', 'accepted': accepted})
                    if mode != 'feedback_off' and accepted <= 0: raise RuntimeError('Sensor rejected')
                if at >= 2500000:
                    emit({'ev': 'plant', 'cycle': at, 'omega': state[:3], 'gimbals': state[3:], 'jets': [jets[5], jets[6]], 'zero': zero})
            if ch in (5, 6): jets[ch] = val
            if ch == 10: zero = int(bool(val & 16))
            cursor = at
        tick += count
        if tick >= 2500000 or tick == end:
            emit({'ev': 'sample', 'cycle': tick, 'imodes33': lib.inspect_ram(0o1303), 'cdu': [lib.inspect_ram(a) for a in (0o32, 0o33, 0o34)], 'failreg': [lib.inspect_ram(a) for a in (0o375, 0o376, 0o377)]})
    proc.stdin.close(); status = proc.wait(); stderr.close(); log.close()
    if status: raise RuntimeError(f'Plant exit {status}')

if __name__ == '__main__': main()