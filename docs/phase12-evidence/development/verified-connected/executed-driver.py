"""Reuse original driver with an external deterministic, bounded plant hook."""
from fractions import Fraction

MCT = Fraction(12,1024000)


def driver_class(p10):
    class Driver(p10.Driver):
        def __init__(self,*args,**kwargs):
            self.plant=None
            self.receiver=None
            self.sensor=None
            self.feedback=False
            self.last_plant_cycle=0
            self.pending=[]
            super().__init__(*args,**kwargs)

        def advance_plant(self, to_cycle):
            if self.plant is None or to_cycle==self.last_plant_cycle:
                return
            dt=float((to_cycle-self.last_plant_cycle)*MCT)
            result=self.plant.step(dt,enabled=self.receiver.enabled,
                                   thrust_n=self.receiver.commanded_thrust_n)
            interval=self.sensor.sample(to_cycle,
                total_acceleration_m_s2=result['total_acceleration_ref_m_s2'],
                gravity_m_s2=result['gravity_ref_m_s2'],connected=True)
            self.pending.extend(interval.events)
            self.last_plant_cycle=to_cycle
            self.emit('plant',cycle=to_cycle,telemetry=result,
                      sensor_interval=interval.to_dict())

        def step(self,count):
            while count:
                chunk=min(count,426) # <5ms coupling; no wall clock.
                used=self.lib.p9_step(chunk)
                if used==0xffffffff:
                    raise ValueError('External observer/packet transport failed; no events discarded')
                pointer=self.lib.p9_events()
                for i in range(used):
                    event=pointer[i]
                    row={'cycle':event.cycle,'pre_bank':event.bank,'pre_z':event.z}
                    if event.kind==4:
                        row.update(ev='input',channel=event.a,value=event.b,accepted_bytes=4,
                                   origin='source-supported external THRUST DINC clock 3200Hz')
                    elif event.kind==1:
                        self.advance_plant(event.cycle)
                        row.update(ev='output',channel=event.a,value=event.b)
                        if self.receiver:
                            old=(self.receiver.enabled,self.receiver.commanded_thrust_n)
                            self.receiver.consume(event.a,event.b)
                            new=(self.receiver.enabled,self.receiver.commanded_thrust_n)
                            if new!=old:
                                self.emit('engine_receiver',cycle=event.cycle,
                                    enabled=new[0],commanded_thrust_n=new[1],
                                    source_channel=event.a,source_value=event.b)
                        if event.a==0o10:
                            self.decoder.apply010(event.b)
                            row['display']=self.decoder.snapshot()
                    else:
                        row.update(ev='transition' if event.kind==2 else 'checkpoint',
                                   snapshot_words=list(event.snapshot))
                        if event.kind==2:row.update(address=event.a,value=event.b)
                        else:row['routine']=self.checkpoints[event.a]
                    self.trace.write(__import__('json').dumps(row,separators=(',',':'))+'\n')
                self.cycle+=chunk
                self.advance_plant(self.cycle)
                for event in self.pending:
                    self.emit('pipa_measurement',requested_cycle=event.cycle,axis=event.axis,
                              counter=event.counter,operation=event.operation,connected=self.feedback,
                              coupling_delay_mct=self.cycle-event.cycle)
                    if self.feedback:self.packet(event.channel,event.operation,'engine-derived PIPA '+event.axis)
                self.pending=[]
                count-=chunk
    return Driver
