/* GPL-2.0-or-later. External throttle clock + read-only observers.
 * The original engine is unchanged. All counter events enter packet_write.
 * THRUST drive: 3200Hz, one request every 80/3 MCT; stop on genuine ZOUT.
 */
#define p9_step retained_observer_step
#define p9_events retained_observer_events
#include "hardware_bridge.c"
#undef p9_step
#undef p9_events
#include "p12_dispatch.h"
extern int packet_write(uint16_t, uint16_t);
static P9Event combined[16384];
static unsigned drive_active, drive_start, drive_index, next_request;

unsigned p9_step(unsigned count) {
  unsigned total = 0;
  for (unsigned n=0; n<count; ++n) {
    unsigned z=inspect_ram(RegZ), bank=effective_bank(z), before=cycle;
    int dispatch=-1, injected=0;
    if (bank!=previous_bank || z!=previous_z)
      if (bank==P12_NEWOPS_BANK && z==P12_NEWOPS_Z)
        for (unsigned j=0;j<P12_INTERPRETED_COUNT;++j)
          if (inspect_ram(P12_LOC)==p12_interpreted_z[j] &&
              (inspect_ram(P12_BANKSET)>>10)==p12_interpreted_bank[j])
            dispatch=p12_interpreted_index[j];
    if (drive_active && cycle>=next_request) {
      if (packet_write(0255,4)!=4) return ~0u;
      injected=1;
      ++drive_index;
      next_request=drive_start+(drive_index*80+2)/3;
    }
    unsigned used=retained_observer_step(1);
    if (used==~0u) return ~0u;
    if (dispatch>=0) observe(3,dispatch,1,bank,z);
    if (total+used_events+injected>16384 || overflowed) return ~0u;
    if (injected) {
      P9Event *e=&combined[total++]; memset(e,0,sizeof(*e));
      e->kind=4; e->cycle=before; e->a=0255; e->b=4; e->bank=bank; e->z=z;
    }
    for (unsigned j=0;j<used_events;++j) {
      P9Event *e=&events[j];
      if (e->kind==1 && e->a==0255 && e->b==017) drive_active=0;
      if (e->kind==1 && e->a==014) {
        if (!(e->b&010)) drive_active=0;
        else if (!drive_active) {
          drive_active=1; drive_start=cycle; drive_index=1;
          next_request=drive_start+27;
        }
      }
    }
    memcpy(combined+total,events,used_events*sizeof(P9Event)); total+=used_events;
  }
  return total;
}
P9Event *p9_events(void) { return combined; }
