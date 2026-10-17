/* GPL-2.0-or-later. Read-only inspection and cycle-locked packet transport. */
#include <stdint.h>
#include "agc_engine.h"
extern agc_t State;
extern void cpu_step(uint32_t);
extern uint32_t packet_read(void);
static uint32_t words[8192], times[8192], used, cycle;
unsigned inspect_ram(unsigned address) {return (uint16_t)State.Erasable[address/0400][address%0400];}
unsigned inspect_channel(unsigned channel) {return State.InputChannel[channel];}
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