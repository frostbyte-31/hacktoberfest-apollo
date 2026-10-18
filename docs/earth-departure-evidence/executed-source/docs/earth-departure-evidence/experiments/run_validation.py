#!/usr/bin/env python3
"""Fresh, cycle-locked native Comanche P52 fixture and causal controls.

Use a new --out directory. Original flight code and emulator inputs are retained
in earlier evidence directories and are never modified. This script may disable
external feedback or MARK hardware edges solely for disconnected-loop controls.
"""
from pathlib import Path
import argparse
import hashlib
import json
import sys

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT))
from backend.cmc_alignment import (prepare_alignment_assets,_AlignmentComputer,STARS,SCOPE)


def run(out,mode="connected",assets=None):
    out=Path(out).resolve();out.mkdir(parents=True,exist_ok=False)
    if assets is None:assets=prepare_alignment_assets(out/"assets")
    c=_AlignmentComputer(assets,out)
    frames=[]
    def observe(label,snapshot=None):
        s=snapshot or c.snapshot()
        frames.append({"label":label,"computer":s})
        return s
    def keys(text):
        for key in text.split():c.key(key)
        c.advance(3)
        return observe(text)
    def move(target):
        # Same bounded controller available in the UI. The last physical
        # deflection can be fractional; no absolute angle/counter writes.
        for _ in range(100):
            delta=target-c.snapshot()["instruments"]["shaftDeg"]
            if abs(delta)<1e-7:return
            c.instrument("optics_slew",{"shaft":max(-1.,min(1.,delta/20)),
                "trunnion":0,"rate":"HIGH","seconds":1})
        raise RuntimeError("Controller movement failed to converge")
    try:
        observe("initialized",c.boot())
        if mode=="feedback-off":c.feedback_enabled=False
        if mode=="mark-irq-off":c.mark_interrupt_enabled=False
        if mode=="imu-off":
            c.instrument("power_imu",False);c.advance(2)
            keys("VERB 3 7 ENTR 5 2 ENTR")
            keys("VERB 0 5 NOUN 0 9 ENTR")
        else:
            keys("VERB 3 7 ENTR 5 2 ENTR")
            keys("VERB 2 2 ENTR 0 0 0 0 3 ENTR PRO")
            keys("ENTR")
            keys("VERB 2 1 ENTR 0 0 0 3 0 ENTR PRO")
            observe("mark30",c.instrument("mark","MARK")["computer"])
            if mode!="mark-irq-off":
                keys("PRO");keys("PRO")
                keys("VERB 2 1 ENTR 0 0 0 3 7 ENTR PRO")
                target=104.4 if mode=="ui-quantized" else STARS[1]["shaftDeg"]
                if mode=="bad-sighting":target-=5
                move(target)
                observe("mark37",c.instrument("mark","MARK")["computer"])
                keys("PRO");keys("PRO")
                keys("PRO")
                if mode!="no-torque-approval":keys("PRO")
                observe("after-settling",c.advance(15))
                if mode!="no-torque-approval":keys("VERB 3 7 ENTR 0 0 ENTR")
            else:observe("missing-edge-wait",c.advance(15))
        final=c.snapshot()
        summary={"mode":mode,"scope":SCOPE,"finalDsky":final["dsky"],
            "alignment":final["instruments"]["alignment"],
            "encoderReadback":final["instruments"]["encoderReadback"],
            "gyroOutputs":final["instruments"]["gyroOutputs"],
            "checkpoints":final["instruments"]["checkpoints"],
            "finalCycle":final["cycle"],"provenance":final["provenance"]}
        (out/"frames.json").write_text(json.dumps(frames,indent=2)+"\n")
        (out/"summary.json").write_text(json.dumps(summary,indent=2)+"\n")
    finally:c.trace.close()
    summary["traceSha256"]=hashlib.sha256((out/"trace.jsonl").read_bytes()).hexdigest()
    (out/"summary.json").write_text(json.dumps(summary,indent=2)+"\n")
    return summary


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out",type=Path,required=True)
    parser.add_argument("--mode",choices=("connected","repeat","feedback-off","mark-irq-off","imu-off","bad-sighting","no-torque-approval","ui-quantized"),default="connected")
    parser.add_argument("--assets",type=Path)
    args=parser.parse_args()
    summary=run(args.out,args.mode,json.loads(args.assets.read_text())if args.assets else None)
    print(json.dumps(summary,indent=2))
