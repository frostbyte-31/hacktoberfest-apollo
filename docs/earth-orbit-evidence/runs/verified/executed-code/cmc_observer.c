/* GPL-2.0-or-later. Read-only packet/cycle observer for original Comanche055.
 * The pinned yaAGC engine and ringbuffer are compiled unchanged. No flight RAM,
 * program counter, alignment flag or sensor counter is modified by this file.
 * Selecting the CM personality is the existing emulator configuration switch.
 */
#include <stdint.h>
#include "yaAGC.h"
#include "agc_engine.h"
#include "ringbuffer.h"
extern agc_t State;
extern void cpu_step(uint32_t);
extern uint32_t packet_read(void);
static uint32_t words[8192];
static uint64_t cycles[8192];
static unsigned used;
void cmc_select(void) { CmOrLm = 1; }
uint64_t cmc_cycle(void) { return State.CycleCounter; }
unsigned cmc_pending(void) {
  return ((ringbuffer_in.head - ringbuffer_in.tail) & (RINGBUFFER_CAPACITY - 1)) / RINGBUFFER_ELEMENT_SIZE;
}
uint32_t cmc_peek(void) {
  if (!cmc_pending()) return UINT32_MAX;
  unsigned char p[4];
  for (unsigned i = 0; i < 4; ++i)
    p[i] = ringbuffer_in.data[(ringbuffer_in.tail + i) & (RINGBUFFER_CAPACITY - 1)];
  int ch, val, mask;
  if (ParseIoPacket(p, &ch, &val, &mask)) return UINT32_MAX;
  return ((uint32_t)(mask != 0) << 31) | ((uint32_t)ch << 16) | (uint32_t)val;
}
unsigned cmc_step(unsigned count) {
  used = 0;
  for (unsigned n = 0; n < count; ++n) {
    cpu_step(1);
    uint32_t p;
    while ((p = packet_read())) {
      if (used == 8192) return UINT32_MAX;
      words[used] = p;
      cycles[used++] = State.CycleCounter;
    }
  }
  return used;
}
uint32_t cmc_word(unsigned n) { return n < used ? words[n] : 0; }
uint64_t cmc_output_cycle(unsigned n) { return n < used ? cycles[n] : 0; }
