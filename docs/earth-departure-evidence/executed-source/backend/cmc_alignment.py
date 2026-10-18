#!/usr/bin/env python3
"""Original Comanche P52 with an external, bounded CSM instrument fixture.

The unmodified rope computes P51's initial reference and every P52 result.
Only documented switch, encoder-counter and MARK interrupt inputs are supplied.
A fixed physical star field is constructed from two original catalog vectors.
This is not an Apollo 11 post-insertion checkpoint or a complete flight model.
"""
from __future__ import annotations
from copy import deepcopy
import ctypes
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import threading
import uuid

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend import cmc_native as native

ROOT = native.ROOT
EVIDENCE = ROOT / "docs/earth-departure-evidence"
BIAS = 19.775390625
GYRO_DEG_PER_PULSE = 360 / 2097152
# Decimal catalog indices24/31, entered as octal30/37. Original STAR_TABLES.agc.
CATALOG = ((-.6898393233, -.4182330640, -.5909338474),
           (+.2069525789, -.8719885748, -.4436288486))
SEPARATION = math.degrees(math.acos(sum(a*b for a,b in zip(*CATALOG))))
TA = 40.0
DELTA_SA = math.degrees(math.acos((math.cos(math.radians(SEPARATION))-
    math.cos(math.radians(TA))**2) / math.sin(math.radians(TA))**2))
STARS = ({"code": "30", "name": "Menkent", "shaftDeg": 0., "trunnionDeg": TA,
          "catalogVector": list(CATALOG[0])},
         {"code": "37", "name": "Nunki", "shaftDeg": DELTA_SA, "trunnionDeg": TA,
          "catalogVector": list(CATALOG[1])})
SCOPE = ("Modeled stationary CSM instruments and fixed original-catalog star field; "
         "P51 establishes this fixture's reference through original optical marks. "
         "Not a restored Apollo 11 Earth-orbit checkpoint, calibrated IMU, orbit dynamics or TLI.")


def alignment_availability():
    value = native.availability()
    observer = EVIDENCE / "experiments/alignment_observer.c"
    if not observer.is_file() or observer.is_symlink():
        value.update(available=False, unavailableReason="CMC alignment hardware observer is missing")
    value.update(scope=SCOPE, instrumentModel="CSM fixed-star alignment fixture")
    return value


def prepare_alignment_assets(output=None):
    assets = native.prepare_cmc_assets(output)
    directory = Path(assets["directory"])
    engine = directory / "source/yaAGC"
    observer = EVIDENCE / "experiments/alignment_observer.c"
    library = directory / "cmc-alignment-engine.so"
    names = ("agc_engine.c", "wasm.c", "agc_engine_init.c", "agc_utilities.c",
             "ringbuffer_api.c", "ringbuffer.c", "rfopen.c")
    command = ["cc", "-shared", "-fPIC", "-O2", "-I"+str(engine), str(observer),
               *[str(engine/name) for name in names], "-lm", "-o", str(library)]
    result = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, timeout=120)
    (directory / "alignment-build.stdout").write_text(result.stdout)
    (directory / "alignment-build.stderr").write_text(result.stderr)
    (directory / "alignment-build-command.json").write_text(json.dumps({"argv":command,"exit":result.returncode},indent=2))
    if result.returncode:
        raise RuntimeError("CMC alignment adapter build failed")
    assets["library"] = str(library.resolve())
    assets["provenance"].update(engineSha256=native._digest(library),
        observerSha256=native._digest(observer), hostFlightMemoryWrites=False,
        scope=SCOPE, externalHardwareInterrupt="KEYRUPT2 after consumed channel016 MARK/REJECT")
    (directory / "alignment-assets.json").write_text(json.dumps(assets,indent=2)+"\n")
    return assets


def _rot(axis, degrees):
    s,c=math.sin(math.radians(degrees)),math.cos(math.radians(degrees))
    if axis==0:return [[1.,0.,0.],[0.,c,-s],[0.,s,c]]
    if axis==1:return [[c,0.,s],[0.,1.,0.],[-s,0.,c]]
    return [[c,-s,0.],[s,c,0.],[0.,0.,1.]]


def _mul(a,b):
    return [[sum(a[i][k]*b[k][j] for k in range(3)) for j in range(3)] for i in range(3)]


def _los(shaft,trunnion):
    s,t=math.radians(shaft),math.radians(trunnion)
    return [math.sin(t)*math.cos(s),math.sin(t)*math.sin(s),math.cos(t)]


def _decode_matrix(words):
    """Read-only DP one's-complement B-1 direction-cosine decoding."""
    def signed(word):
        return -(32767-word) if word&16384 else word
    values=[2*(signed(words[i])+signed(words[i+1])/16384)/16384 for i in range(0,18,2)]
    return [values[i:i+3] for i in (0,3,6)]


class _AlignmentComputer(native._NativeComputer):
    def __init__(self,assets,output):
        self.imu_powered=False
        self.optics_mode="MANUAL"
        self.shaft=0.
        self.trunnion=BIAS
        self.gimbals=[0.,0.,0.]
        self.encoder_counts={0o32:0,0o33:0,0o34:0,0o35:0,0o36:0}
        self.marks=[]
        self.torque_outputs=[]
        self.sensor_operations=0
        self.gyro_sensor_operations=0
        self.feedback_enabled=True
        self.mark_interrupt_enabled=True
        self.star_fit=None
        self.bootstrap=False
        self.reference_initialized=False
        self.p52_marks=0
        self.torque_approved=False
        self.p52_complete=False
        self.completion_cycle=None
        self._coupling=False
        self._pending_feedback=[]
        self._init_completed=False
        self._observed_program=None
        self.checkpoints=[]
        super().__init__(assets,output)
        for name in ("cmc_read","cmc_channel","cmc_mark_edge"):
            getattr(self.lib,name).restype=ctypes.c_uint32
        self.lib.cmc_read.argtypes=[ctypes.c_uint32]
        self.lib.cmc_channel.argtypes=[ctypes.c_uint32]

    def _step(self,count):
        remaining=count
        while remaining:
            size=min(remaining,853)
            used=self.lib.cmc_step(size)
            if used==0xffffffff:raise RuntimeError("Alignment output overflow")
            for i in range(used):
                word=self.lib.cmc_word(i)
                channel,value=word>>16,word&32767
                cycle=self.lib.cmc_output_cycle(i)
                self.decoder.apply(channel,value,cycle)
                self._emit({"ev":"output","cycle":cycle,"channel":channel,"value":value})
                if channel==0o177 and value&0o3777:
                    self._gyro(value,cycle)
                if channel in (0o174,0o175,0o176) and value:
                    raise RuntimeError("Coarse IMU motion is outside this fine-alignment fixture")
            if self._pending_feedback and not self._coupling:
                self._coupling=True
                try:
                    pending,self._pending_feedback=self._pending_feedback,[]
                    for counter,direction in pending:
                        if self.feedback_enabled:
                            self._packet(0x80|counter,0o21 if direction>0 else 0o23)
                            self.sensor_operations+=1
                            self.gyro_sensor_operations+=1
                finally:self._coupling=False
            remaining-=size
        self._observe()

    def _gyro(self,value,cycle):
        axis_bits=value&0o30000
        axis={0o10000:0,0o20000:1,0o30000:2}.get(axis_bits)
        if axis is None:raise RuntimeError("Unselected gyro pulse is unsupported")
        pulses=(value&0o3777)*(-1 if value&0o40000 else 1)
        delta=pulses*GYRO_DEG_PER_PULSE
        if abs(delta)>1:raise RuntimeError("Gyro pulse exceeds bounded fine-alignment range")
        # Stable-member torquing, with the CSM's left-handed X/Z/Y gimbals.
        gx,gy,gz=self.gimbals
        matrix=_mul(_mul(_rot(0,-gx),_rot(2,-gz)),_rot(1,-gy))
        matrix=_mul(matrix,_rot(axis,delta))
        new=[-math.degrees(math.atan2(matrix[2][1],matrix[1][1])),
             -math.degrees(math.atan2(matrix[0][2],matrix[0][0])),
             math.degrees(math.asin(max(-1.,min(1.,matrix[0][1]))))]
        if max(abs(v)for v in new)>5:
            raise RuntimeError("Gimbal motion exceeds this five-degree fine-alignment fixture")
        self.gimbals=new
        for index,angle in enumerate(new):
            counter=0o32+index
            target=round(angle*32768/360)
            current=self.encoder_counts[counter]
            difference=target-current
            if abs(difference)>512:raise RuntimeError("Excessive physical sensor delta")
            self._pending_feedback.extend([(counter,1 if difference>0 else -1)]*abs(difference))
            self.encoder_counts[counter]=target
        row={"cycle":cycle,"channel":0o177,"value":value,"axis":"XYZ"[axis],
             "pulses":pulses,"deltaDeg":delta,"gimbalsDeg":list(new)}
        self.torque_outputs.append(row)
        self._emit({"ev":"gyro_model",**row})

    def _observe(self):
        if not self._init_completed:return
        d=self.decoder.snapshot()
        original_ref=bool(self.lib.cmc_read(0o77)&0o10000)
        self.reference_initialized=original_ref
        if d['PROG']=='52' and self._observed_program!='52':
            self.p52_marks=0
            self.torque_approved=False
            self.p52_complete=False
            self.completion_cycle=None
            self.star_fit=None
            self.torque_outputs=[]
            self.gyro_sensor_operations=0
        self._observed_program=d['PROG']
        if not self.bootstrap and d['PROG']=='52' and d['VERB']=='06' and d['NOUN']=='05' and d['R1'].isdigit():
            if self.star_fit is None:
                self.star_fit={"kind":"p52-star-fit","cycle":self.lib.cmc_cycle(),"dsky":d}
                self.checkpoints.append(deepcopy(self.star_fit))
                self._emit({"ev":"p52_star_fit",**self.star_fit})
        readback=[self.lib.cmc_read(0o32+i) for i in range(3)]
        expected=[self.encoder_counts[0o32+i]&0o77777 for i in range(3)]
        if (not self.bootstrap and self.torque_approved and self.p52_marks>=2 and self.torque_outputs
                and self.gyro_sensor_operations>0 and readback==expected and self.star_fit
                and int(self.star_fit['dsky']['R1'])<=5 and self.imu_powered):
            if d["PROG"]=="52" and d["VERB"]=="50" and d["NOUN"]=="25" and d["R1"]=="00014":
                if not self.p52_complete:
                    self.p52_complete=True
                    self.completion_cycle=self.lib.cmc_cycle()
                    self.checkpoints.append({"kind":"p52-completion-display","cycle":self.completion_cycle,"dsky":d})
                    self._emit({"ev":"p52_completion",**self.checkpoints[-1]})

    def _set_switch(self,channel,mask,value):
        packets=[self._packet(channel|0x100,mask),self._packet(channel,value)]
        self._emit({"ev":"switch","channel":channel,"mask":mask,"value":value,"packets":packets})

    def _move(self,shaft,trunnion,seconds=None):
        # Physical encoder motion is scheduled across CPU time, rather than
        # burst-writing an absolute angle. Every increment uses the original
        # ringbuffer counter-operation path; no counter register is assigned.
        if not -270<=shaft<=270 or not 0<=trunnion<=64.7:
            raise ValueError("Optics angle is outside this bounded encoder fixture")
        targets={0o36:round(shaft*32768/360),0o35:round((trunnion-BIAS)*32768/90)}
        differences={counter:target-self.encoder_counts[counter]for counter,target in targets.items()}
        if max(abs(v)for v in differences.values())>50000:raise ValueError("Optics movement exceeds fixture limit")
        if seconds is None:
            seconds=max(.1,abs(shaft-self.shaft)/20,abs(trunnion-self.trunnion)/10)
        count=max(abs(v)for v in differences.values())
        start=self.lib.cmc_cycle()
        duration=round(seconds/native.PERIOD)
        sent={counter:0 for counter in targets}
        for index in range(count):
            for counter,difference in differences.items():
                required=round((index+1)*abs(difference)/count)
                if required>sent[counter]:
                    self._packet(0x80|counter,1 if difference>0 else 3)
                    self.sensor_operations+=1
                    sent[counter]+=1
            goal=start+round((index+1)*duration/count)
            if self.lib.cmc_cycle()>goal:
                raise RuntimeError("Optical encoder rate exceeds bounded hardware coupling")
            self._step(goal-self.lib.cmc_cycle())
        if not count:self._step(duration)
        self.encoder_counts.update(targets)
        self.shaft=shaft
        self.trunnion=trunnion
        self._emit({"ev":"optics_position","cycle":self.lib.cmc_cycle(),"shaftDeg":shaft,
                    "trunnionDeg":trunnion,"encoderCounts":deepcopy(self.encoder_counts),
                    "startedAtCycle":start,"durationCpuSeconds":seconds})

    def _keys(self,text):
        for key in text.split():self.key(key)
        self.advance(3)

    def boot(self):
        if self.booted:raise ValueError("CMC already booted")
        self.bootstrap=True
        self.booted=True
        self.advance(5)
        self._set_switch(0o30,0o400,0)
        self.imu_powered=True
        self.advance(15)
        self._keys("RSET VERB 3 7 ENTR 5 1 ENTR")
        self._keys("PRO")
        for index,star in enumerate(STARS):
            self._move(star["shaftDeg"],star["trunnionDeg"])
            self.instrument("mark","MARK")
            self._keys("PRO")
            self._keys("VERB 2 1 ENTR "+" ".join("000"+star["code"])+" ENTR PRO")
        d=self.decoder.snapshot()
        if d["VERB"]!="06" or d["NOUN"]!="05" or not d["R1"].isdigit() or int(d["R1"])>5:
            raise RuntimeError("Original P51 star separation did not validate the physical fixture: "+str(d))
        self.checkpoints.append({"kind":"p51-star-fit","cycle":self.lib.cmc_cycle(),"dsky":d})
        self._keys("PRO")
        if not self.lib.cmc_read(0o77)&0o10000:raise RuntimeError("Original P51 did not initialize REFSMMAT")
        self.reference_initialized=True
        self._keys("VERB 3 7 ENTR 0 0 ENTR")
        self._move(STARS[0]["shaftDeg"],STARS[0]["trunnionDeg"])
        self.bootstrap=False
        self._init_completed=True
        self._observed_program=self.decoder.snapshot()["PROG"]
        self._emit({"ev":"fixture_initialized","cycle":self.lib.cmc_cycle(),"scope":SCOPE,
                    "referenceComputedBy":"Original P51 optical observations","checkpoints":self.checkpoints})
        self.trace.flush()
        return self.snapshot()

    def key(self,key):
        before=self.decoder.snapshot()
        if not self.bootstrap and key=="PRO" and before["PROG"]=="52" and before["VERB"]=="06" and before["NOUN"]=="93":
            self.torque_approved=True
            self.checkpoints.append({"kind":"p52-torque-review","cycle":self.lib.cmc_cycle(),"dsky":before})
        return super().key(key)

    def instrument(self,action,value):
        if not self.booted:raise ValueError("Boot the CMC first")
        at=self.lib.cmc_cycle()
        if action=="power_imu":
            if type(value)is not bool:raise ValueError("IMU power must be boolean")
            self._set_switch(0o30,0o400,0 if value else 0o400)
            self.imu_powered=value
            if not value:self.p52_complete=False
            self.advance(.5)
        elif action=="optics_mode":
            if value not in ("MANUAL","ZERO","CMC"):raise ValueError("Unsupported optics mode")
            if value=="CMC":raise ValueError("Automatic optical motor drive is unavailable in this manual fixture")
            self._set_switch(0o33,0o30,0o30 if value=="MANUAL" else 0o20)
            self.optics_mode=value
            if value=="ZERO":
                self._move(0.,0.)
                self.advance(20)
                for counter in (0o35,0o36):
                    raw=self.lib.cmc_read(counter)
                    self.encoder_counts[counter]=raw if raw<16384 else raw-32768
                self.shaft=self.encoder_counts[0o36]*360/32768
                self.trunnion=BIAS+self.encoder_counts[0o35]*90/32768
            else:self.advance(.5)
        elif action=="optics_slew":
            if self.optics_mode!="MANUAL":raise ValueError("Set optics to MANUAL before using the OHC")
            if not isinstance(value,dict) or set(value)!={"shaft","trunnion","rate","seconds"}:raise ValueError("Invalid OHC movement")
            for name in ("shaft","trunnion","seconds"):
                if type(value[name])not in(int,float)or not math.isfinite(value[name]):raise ValueError("OHC movement must be finite")
            if abs(value["shaft"])>1 or abs(value["trunnion"])>1 or not 0<value["seconds"]<=1:raise ValueError("OHC deflection/duration is outside bounds")
            if value["rate"] not in("LOW","HIGH"):raise ValueError("Unknown OHC rate")
            rate=.2 if value["rate"]=="LOW" else 20.
            trunnion_rate=.1 if value["rate"]=="LOW" else 10.
            self._move(max(-270.,min(270.,self.shaft+value["shaft"]*rate*value["seconds"])),
                       max(0.,min(64.7,self.trunnion+value["trunnion"]*trunnion_rate*value["seconds"])),
                       seconds=value["seconds"])
        elif action=="mark":
            if value not in("MARK","REJECT"):raise ValueError("Unknown optical mark action")
            word=0o40 if value=="MARK" else 0o100
            packet=self._packet(0o16,word)
            if self.mark_interrupt_enabled and not self.lib.cmc_mark_edge():raise RuntimeError("Physical MARK edge was not accepted")
            cycle=self.lib.cmc_cycle()
            self._emit({"ev":"hardware_interrupt","interrupt":6,"cycle":cycle,"channel":0o16,"value":word,"delivered":self.mark_interrupt_enabled})
            if value=="MARK":
                row={"cycle":cycle,"shaftDeg":self.shaft,"trunnionDeg":self.trunnion,
                     "gimbalsDeg":list(self.gimbals),"program":self.decoder.snapshot()["PROG"],
                     "bootstrap":self.bootstrap,"packet":packet}
                self.marks.append(row)
                if not self.bootstrap and row["program"]=="52":self.p52_marks+=1
            self.advance(.2)
            self._packet(0o16,0)
            self.advance(.5)
        else:raise ValueError("Unsupported CSM instrument control")
        self._emit({"ev":"instrument_action","action":action,"value":value,"queuedAtCycle":at,"afterCycle":self.lib.cmc_cycle()})
        self.trace.flush()
        return {"computer":self.snapshot(),"ackpacket":{"action":action,"value":value,"queuedAtCycle":at,"afterCycle":self.lib.cmc_cycle()}}

    def snapshot(self):
        result=super().snapshot()
        result["provenance"]["scope"]=SCOPE
        line=_los(self.shaft,self.trunnion)
        stars=[]
        for star in STARS:
            s=deepcopy(star)
            target=_los(star["shaftDeg"],star["trunnionDeg"])
            s["errorDeg"]=math.degrees(math.acos(max(-1.,min(1.,sum(a*b for a,b in zip(line,target))))))
            stars.append(s)
        matrix_words=[self.lib.cmc_read(3*256+0o335+i)for i in range(18)]
        result["instruments"]={"mode":"MODELED CSM INSTRUMENTS","imuPowered":self.imu_powered,
            "opticsMode":self.optics_mode,"shaftDeg":self.shaft,"trunnionDeg":self.trunnion,
            "mechanicalTrunnionDeg":self.trunnion-BIAS,"gimbalsDeg":list(self.gimbals),
            "stars":stars,"markCount":len(self.marks),"marks":deepcopy(self.marks[-12:]),
            "sensorOperations":self.sensor_operations,"scope":SCOPE,
            "ohcRateScope":"DIRECT OHC: bounded LOW shaft0.2/trunnion0.1deg/s; HIGH maximum shaft20/trunnion10deg/s. Low gain is an engineering assumption, not flight calibration.",
            "encoderReadback":{"CDUX":self.lib.cmc_read(0o32),"CDUY":self.lib.cmc_read(0o33),"CDUZ":self.lib.cmc_read(0o34),"CDUT":self.lib.cmc_read(0o35),"CDUS":self.lib.cmc_read(0o36)},
            "referenceMatrixWords":matrix_words,
            "referenceMatrix":{"values":_decode_matrix(matrix_words),"valid":self.reference_initialized,
                "units":"dimensionless direction cosines","frame":"basic reference to stable member",
                "source":"Original Comanche erasable E3,1735 through E3,1756, read only",
                "cycle":self.lib.cmc_cycle()},
            "feedbackEnabled":self.feedback_enabled,
            "alignment":{"referenceInitialized":self.reference_initialized,"p52Complete":self.p52_complete,
                "p52Marks":self.p52_marks,"torqueApproved":self.torque_approved,
                "torqueOutputCount":len(self.torque_outputs),"completionCycle":self.completion_cycle,
                "gyroSensorFeedbackOperations":self.gyro_sensor_operations},
            "checkpoints":deepcopy(self.checkpoints),"gyroOutputs":deepcopy(self.torque_outputs[-20:])}
        return result


class CmcAlignmentProcess(native.CmcProcess):
    def __init__(self,assets,output=None):
        self.assets=assets
        self.output=Path(output)if output is not None else ROOT/".build/earth-departure/sessions"/uuid.uuid4().hex
        if self.output.is_symlink()or self.output.exists():raise ValueError("Alignment session output must be a new directory")
        self.output.mkdir(parents=True)
        spec=self.output/"assets.json";spec.write_text(json.dumps(assets))
        self.stderr=(self.output/"worker.stderr").open("x")
        self.proc=subprocess.Popen([sys.executable,"-B",str(Path(__file__).resolve()),"--worker",str(spec)],
            stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=self.stderr,bufsize=0,cwd=ROOT)
        self._response_buffer=b"";self._lock=threading.Lock();self.closed=False

    def instrument(self,action,value):
        return self._request("instrument",control=action,value=value)


def _worker(spec):
    computer=_AlignmentComputer(json.loads(spec.read_text()),spec.parent)
    os.set_blocking(sys.stdin.fileno(),True)
    try:
        for line in sys.stdin:
            try:
                req=json.loads(line);action=req.get("action")
                if action=="boot":result=computer.boot()
                elif action=="key":result=computer.key(req.get("key"))
                elif action=="advance":result=computer.advance(req.get("seconds"))
                elif action=="instrument":result=computer.instrument(req.get("control"),req.get("value"))
                else:raise ValueError("Unsupported alignment worker action")
                response={"ok":True,"result":result}
            except(ValueError,RuntimeError,TypeError)as exc:response={"ok":False,"error":str(exc)}
            print(json.dumps(response,separators=(",",":")),flush=True)
    finally:computer.trace.close()


if __name__=="__main__":
    if len(sys.argv)==3 and sys.argv[1]=="--worker":_worker(Path(sys.argv[2]))
    else:raise SystemExit("Internal CMC alignment worker; start the application normally.")
