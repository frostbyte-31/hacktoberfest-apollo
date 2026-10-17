/* GPL-2.0-or-later. Diagnostic transport probe, no emulator state writes.
 * Including the unchanged pinned translation unit makes its static FIFO visible
 * to these read-only inspectors. The upstream source is compiled exactly once;
 * no preprocessor symbols replace its functions or change flight behavior. */
#include "agc_engine.c"
#include "ringbuffer.h"
extern agc_t State;
extern void cpu_step(uint32_t);
extern uint32_t packet_read(void);

uint64_t diag_cycle(void) { return State.CycleCounter; }
unsigned diag_cdu(unsigned axis) { return (uint16_t)State.Erasable[0][032 + axis]; }
unsigned diag_entries(void) { return CduFifos[0].Size; }
unsigned diag_checker(void) { return CduChecker; }
uint64_t diag_deadline(void) { return CduFifos[0].NextUpdate; }
unsigned diag_head_code(void) {
  if (CduFifos[0].Size == 0) return 0;
  uint32_t flags = (uint32_t)CduFifos[0].Counts[CduFifos[0].Ptr];
  return 1u | ((flags & 0x40000000u) ? 2u : 0u) |
         ((flags & 0x80000000u) ? 16u : 0u);
}
unsigned diag_pending(void) {
  unsigned total = 0;
  for (int i = 0; i < CduFifos[0].Size; ++i)
    total += (uint32_t)CduFifos[0].Counts[(CduFifos[0].Ptr + i) % MAX_CDU_FIFO_ENTRIES] & 0x3fffffffu;
  return total;
}
unsigned diag_incoming(void) {
  return ((ringbuffer_in.head - ringbuffer_in.tail) & (RINGBUFFER_CAPACITY - 1)) / RINGBUFFER_ELEMENT_SIZE;
}
void diag_step(unsigned count) {
  while (count--) {
    cpu_step(1);
    while (packet_read()) {} /* Drain actual output; never inject actuator data. */
  }
}
