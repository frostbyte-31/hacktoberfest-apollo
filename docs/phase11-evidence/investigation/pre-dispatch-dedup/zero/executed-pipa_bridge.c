/* GPL-2.0-or-later. Extend the retained read-only observer, never the engine.
 * CALCRVG is interpreted code: its address is LOC, not the native CPU Z.
 * Observe original NEWOPS dispatch with matching object bank and LOC.
 */
#define p9_step phase9_original_step
#define p9_events phase9_original_events
#include "hardware_bridge.c"
#undef p9_step
#undef p9_events
#include "p11_dispatch.h"

static P9Event combined[16384];

unsigned p9_step(unsigned count) {
  unsigned total = 0;
  for (unsigned n = 0; n < count; ++n) {
    unsigned z = inspect_ram(RegZ), bank = effective_bank(z);
    int dispatch = bank == P11_NEWOPS_BANK && z == P11_NEWOPS_Z &&
      inspect_ram(P11_LOC) == P11_CALCRVG_Z &&
      (inspect_ram(P11_BANKSET) >> 10) == P11_CALCRVG_BANK;
    unsigned used = phase9_original_step(1);
    if (used == ~0u) return ~0u;
    if (dispatch) observe(3, P11_CALCRVG_INDEX, 1, bank, z);
    if (overflowed || total + used_events > 16384) return ~0u;
    memcpy(combined + total, events, used_events * sizeof(P9Event));
    total += used_events;
  }
  return total;
}
P9Event *p9_events(void) { return combined; }
