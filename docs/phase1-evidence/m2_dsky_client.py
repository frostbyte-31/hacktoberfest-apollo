#!/usr/bin/env python3
"""Phase 1 / M2 headless DSKY client for yaAGC.

Every constant below was checked against the pinned source tree
(virtualagc f577e3fd917866c59334e6cdd32504f09df76f60):
  - Packet format: yaAGC/agc_utilities.c FormIoPacket/ParseIoPacket
  - Keycodes: Luminary099/PINBALL_GAME__BUTTONS_AND_LIGHTS.agc lines 383-395
              (also yaDSKY2/yaDSKY2.cpp OutputKeycode calls)
  - Keys are written to channel 015, which raises KEYRUPT1: yaAGC/SocketAPI.c line 240
  - Display relay word on channel 010, AAAABCCCCCDDDDD: PINBALL lines 398-403;
    the digit relay codes are the low 5 bits of RELTAB in FIXED-FIXED_CONSTANT_POOL.agc;
    the row (AAAA) mapping comes from yaDSKY2.cpp lines 1953-2083.

The client only sends keystrokes and logs what the emulator sends back.
It does no AGC computation.
"""
import json, socket, sys, time

KEY = {str(d): d for d in range(1, 10)}
KEY.update({"0": 16, "V": 17, "R": 18, "K": 25, "+": 26, "-": 27, "E": 28, "C": 30, "N": 31})
# RELTAB low-5-bit relay codes -> character
SEG = {0: " ", 21: "0", 3: "1", 25: "2", 27: "3", 15: "4", 30: "5", 28: "6", 19: "7", 29: "8", 31: "9"}
# AAAA -> (left field, right field)
ROW = {11: ("MD1", "MD2"), 10: ("VD1", "VD2"), 9: ("ND1", "ND2"), 8: (None, "R1D1"),
       7: ("R1D2", "R1D3"), 6: ("R1D4", "R1D5"), 5: ("R2D1", "R2D2"), 4: ("R2D3", "R2D4"),
       3: ("R2D5", "R3D1"), 2: ("R3D2", "R3D3"), 1: ("R3D4", "R3D5")}

def form(ch, val):
    return bytes([ch >> 3, 0x40 | ((ch << 3) & 0x38) | ((val >> 12) & 7),
                  0x80 | ((val >> 6) & 0x3F), 0xC0 | (val & 0x3F)])

def parse(p):
    if (p[0] & 0xC0, p[1] & 0xC0, p[2] & 0xC0, p[3] & 0xC0) != (0, 0x40, 0x80, 0xC0):
        return None
    ch = ((p[0] & 0x1F) << 3) | ((p[1] >> 3) & 7)
    val = ((p[1] << 12) & 0x7000) | ((p[2] << 6) & 0x0FC0) | (p[3] & 0x3F)
    return ch, val

disp = {f: "?" for pair in ROW.values() for f in pair if f}
sign = {"R1": "", "R2": "", "R3": ""}

def apply010(val):
    a = (val >> 11) & 0xF
    if a not in ROW:
        return
    l, r = ROW[a]
    lc, rc = (val >> 5) & 0x1F, val & 0x1F
    if l: disp[l] = SEG.get(lc, f"<{lc}>")
    disp[r] = SEG.get(rc, f"<{rc}>")

def snapshot():
    g = lambda *k: "".join(disp[x] for x in k)
    return {"PROG": g("MD1", "MD2"), "VERB": g("VD1", "VD2"), "NOUN": g("ND1", "ND2"),
            "R1": g("R1D1", "R1D2", "R1D3", "R1D4", "R1D5"),
            "R2": g("R2D1", "R2D2", "R2D3", "R2D4", "R2D5"),
            "R3": g("R3D1", "R3D2", "R3D3", "R3D4", "R3D5")}

def main(port, script, out):
    s = socket.create_connection(("127.0.0.1", port), timeout=5)
    s.settimeout(0.05)
    t0 = time.time(); buf = b""; log = open(out, "w")
    def emit(rec):
        rec["t"] = round(time.time() - t0, 3); log.write(json.dumps(rec) + "\n"); log.flush()
    def pump(secs):
        nonlocal buf
        end = time.time() + secs
        while time.time() < end:
            try:
                d = s.recv(4096)
                if not d: emit({"ev": "socket_closed"}); return
                buf += d
            except socket.timeout:
                continue
            while len(buf) >= 4:
                p = parse(buf[:4])
                if p is None: buf = buf[1:]; continue  # resync per ParseIoPacket rules
                buf = buf[4:]
                ch, val = p
                rec = {"ev": "rx", "ch": oct(ch), "val": oct(val)}
                if ch == 0o10:
                    apply010(val); rec["display"] = snapshot()
                emit(rec)
    for step in script:
        if step[0] == "wait":
            pump(step[1])
        else:
            for k in step[1]:
                emit({"ev": "tx_key", "key": k, "ch": "0o15", "val": oct(KEY[k])})
                s.sendall(form(0o15, KEY[k])); pump(0.4)
    emit({"ev": "final", "display": snapshot()})

if __name__ == "__main__":
    port = int(sys.argv[1]); out = sys.argv[2]
    script = [("wait", 5), ("keys", "V35E"), ("wait", 8), ("keys", "R"),
              ("keys", "V16N36E"), ("wait", 6)]
    main(port, script, out)
