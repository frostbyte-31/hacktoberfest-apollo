/* GPL-2.0-or-later. Phase 9 bridge: Phase 5 plant_bridge.c plus the AOT mark
 * button input. The ringbuffer/socket API has no path that raises KEYRUPT2
 * for channel 016 (ringbuffer_api.c:142-163 requests KEYRUPT1 for channel 015
 * and UPRUPT for 0173 only), so the mark discrete and its interrupt are
 * delivered here exactly as the hardware does: write NAVKEYIN (channel 016)
 * and request KEYRUPT2 (interrupt index 6; INTERRUPT_LEAD_INS.agc:65-68
 * branches KEYRUPT2 to MARKRUPT). No flight code or emulator code is changed;
 * no AGC memory is written by this bridge. */
#include <stdint.h>
#include "agc_engine.h"
extern agc_t State;
extern void cpu_step(uint32_t);
extern uint32_t packet_read(void);
static uint32_t words[8192], times[8192], used, cycle;
unsigned inspect_ram(unsigned address) {return (uint16_t)State.Erasable[address/0400][address%0400];}
unsigned inspect_channel(unsigned channel) {return State.InputChannel[channel];}
void mark_write(unsigned bits, unsigned with_interrupt) {
  State.InputChannel[016] = bits & 077777;
  if (with_interrupt) State.InterruptRequests[6] = 1; /* KEYRUPT2 -> MARKRUPT */
}
unsigned step_chunk(unsigned count) {
 used=0;
 for(unsigned i=0;i<count;i++) {
  cpu_step(1); cycle++;
  uint32_t p;
  while((p=packet_read())) {
   if(used>=8192)return 0xffffffffu;
   words[used]=p;times[used++]=cycle;
  }
 }
 return used;
}
unsigned output_word(unsigned i) {return i<used?words[i]:0;}
unsigned output_cycle(unsigned i) {return i<used?times[i]:0;}
