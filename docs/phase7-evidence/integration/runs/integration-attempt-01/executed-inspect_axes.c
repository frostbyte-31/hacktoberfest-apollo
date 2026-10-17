/* GPL-2.0-or-later. Read-only multi-axis inspection over retained core.
 * The included milestone2 bridge includes unchanged agc_engine.c exactly once.
 * No emulator, flight-memory, counter or ringbuffer mutation is added here. */
#include "inspect_bridge.c"

unsigned p7_entries(unsigned axis) { return axis < 3 ? CduFifos[axis].Size : 0; }
unsigned p7_pending(unsigned axis) {
  unsigned total = 0;
  if (axis >= 3) return 0;
  CduFifo_t *fifo = &CduFifos[axis];
  for (int i = 0; i < fifo->Size; ++i)
    total += (uint32_t)fifo->Counts[(fifo->Ptr + i) % MAX_CDU_FIFO_ENTRIES] & 0x3fffffffu;
  return total;
}
unsigned p7_head(unsigned axis) {
  if (axis >= 3 || CduFifos[axis].Size == 0) return 0;
  uint32_t flags = (uint32_t)CduFifos[axis].Counts[CduFifos[axis].Ptr];
  return 1u | ((flags & 0x40000000u) ? 2u : 0u) | ((flags & 0x80000000u) ? 16u : 0u);
}
uint64_t p7_deadline(unsigned axis) { return axis < 3 ? CduFifos[axis].NextUpdate : 0; }
void p7_snapshot(uint64_t *values) {
  values[0] = State.CycleCounter;
  for (unsigned i = 0; i < 3; ++i) values[1 + i] = (uint16_t)State.Erasable[0][032 + i];
  values[4] = diag_incoming(); values[5] = CduChecker;
  for (unsigned i = 0; i < 3; ++i) {
    values[6 + 4*i] = p7_entries(i);
    values[7 + 4*i] = p7_pending(i);
    values[8 + 4*i] = p7_head(i);
    values[9 + 4*i] = p7_deadline(i);
  }
}
/* Peek and parse actual queued bytes without advancing the input tail.
 * Bit31 mask flag; bits16..24 channel (including counter bit); bits0..14 value.
 * UINT32_MAX means missing/malformed, not an encoded valid packet. */
uint32_t p7_peek(unsigned index) {
  if (index >= diag_incoming()) return UINT32_MAX;
  unsigned char packet[4];
  unsigned start = (ringbuffer_in.tail + index * RINGBUFFER_ELEMENT_SIZE) & (RINGBUFFER_CAPACITY - 1);
  for (unsigned i = 0; i < 4; ++i)
    packet[i] = ringbuffer_in.data[(start + i) & (RINGBUFFER_CAPACITY - 1)];
  int channel, value, mask;
  if (ParseIoPacket(packet, &channel, &value, &mask)) return UINT32_MAX;
  return ((uint32_t)(mask != 0) << 31) | ((uint32_t)channel << 16) | (uint32_t)value;
}
void p7_execution(uint64_t *values) {
  /* RegZ/EB/FB/BB come from unchanged agc_engine.h, not invented mappings. */
  values[0] = (uint16_t)State.Erasable[0][RegZ];
  values[1] = (uint16_t)State.Erasable[0][RegEB];
  values[2] = (uint16_t)State.Erasable[0][RegFB];
  values[3] = (uint16_t)State.Erasable[0][RegBB];
  values[4] = (uint32_t)State.NextZ;
  values[5] = (uint16_t)State.Erasable[01011 / 0400][01011 % 0400];
  values[6] = (uint16_t)State.Erasable[01302 / 0400][01302 % 0400];
  values[7] = (uint16_t)State.Erasable[01303 / 0400][01303 % 0400];
  for (unsigned i = 0; i < 3; ++i) values[8 + i] = (uint16_t)State.Erasable[0][0375 + i];
  values[11] = (uint16_t)State.Erasable[0][0111];
  values[12] = (uint16_t)State.InputChannel[07];
}
