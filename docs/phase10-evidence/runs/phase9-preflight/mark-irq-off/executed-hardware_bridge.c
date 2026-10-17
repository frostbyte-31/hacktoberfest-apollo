/* GPL-2.0-or-later. External Phase9 hardware-event fixture + read-only observer.
 * Includes the unchanged Phase5 bridge; no original engine/flight source edits.
 * Channel016 alone does not request KEYRUPT2 in the pinned ringbuffer backend.
 * The one new hardware input asserts the documented interrupt6 interrupt latch
 * AFTER a real channel016 mark packet was consumed. It never writes erasable
 * memory or sets alignment flags. Release is a normal channel016 packet.
 */
#include "plant_bridge.c"
#include "p9_watch.h"
#include <string.h>

typedef struct {
  uint32_t kind, cycle, a, b, bank, z, snapshot[P9_SNAPSHOT_COUNT];
} P9Event;
static P9Event events[16384];
static unsigned used_events, overflowed, previous_bank, previous_z;
static unsigned previous_values[P9_WATCH_COUNT];

static unsigned effective_bank(unsigned z) {
  if (z >= 06000) return 3;
  if (z >= 04000) return 2;
  unsigned bank = inspect_ram(RegFB) >> 10;
  if (bank >= 030 && (inspect_channel(07) & 0100)) bank += 010;
  return bank;
}
static void observe(unsigned kind, unsigned a, unsigned b, unsigned bank, unsigned z) {
  if (used_events >= 16384) { overflowed = 1; return; }
  P9Event *event = &events[used_events++];
  memset(event, 0, sizeof(*event));
  event->kind = kind; event->cycle = cycle;
  event->a = a; event->b = b; event->bank = bank; event->z = z;
  if (kind != 1) for (unsigned i = 0; i < P9_SNAPSHOT_COUNT; ++i)
    event->snapshot[i] = inspect_ram(p9_snapshot_addresses[i]);
}
void p9_observer_init(void) {
  for (unsigned i = 0; i < P9_WATCH_COUNT; ++i)
    previous_values[i] = inspect_ram(p9_watch_addresses[i]);
  previous_bank = previous_z = ~0u;
}
unsigned p9_step(unsigned count) {
  used_events = overflowed = 0;
  for (unsigned n = 0; n < count; ++n) {
    unsigned z = inspect_ram(RegZ), bank = effective_bank(z);
    unsigned packets = step_chunk(1);
    if (packets == ~0u) return ~0u;
    for (unsigned i = 0; i < packets; ++i) {
      uint32_t word = output_word(i);
      observe(1, word >> 16, word & 077777, bank, z);
    }
    if (bank != previous_bank || z != previous_z)
      for (unsigned i = 0; i < P9_CHECKPOINT_COUNT; ++i)
        if (p9_checkpoint_banks[i] == bank && p9_checkpoint_z[i] == z)
          observe(3, i, 0, bank, z);
    previous_bank = bank; previous_z = z;
    for (unsigned i = 0; i < P9_WATCH_COUNT; ++i) {
      unsigned value = inspect_ram(p9_watch_addresses[i]);
      if (value != previous_values[i]) {
        observe(2, p9_watch_addresses[i], value, bank, z);
        previous_values[i] = value;
      }
    }
  }
  return overflowed ? ~0u : used_events;
}
P9Event *p9_events(void) { return events; }
int p9_mark_interrupt(void) {
  unsigned word = inspect_channel(016);
  if ((word != 4 && word != 8) || State.InterruptRequests[6]) return 0;
  State.InterruptRequests[6] = 1; /* External KEYRUPT2 hardware event only. */
  return 1;
}
