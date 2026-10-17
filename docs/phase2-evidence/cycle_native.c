/* Test driver only: unmodified upstream wasm.c and ringbuffer backend, compiled
 * natively. GPL-2.0-or-later like the linked Virtual AGC sources. */
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include "agc_engine.h"
extern agc_t State;
extern void cpu_reset(void), set_fixed(unsigned char*), cpu_step(uint32_t);
extern int packet_write(uint16_t,uint16_t);
extern uint32_t packet_read(void);
static uint32_t hash = 2166136261u;
static void mix(uint16_t w) { hash = (hash ^ (w & 255)) * 16777619u; hash = (hash ^ (w >> 8)) * 16777619u; }
int main(int argc, char **argv) {
  if(argc != 3) return 2;
  FILE *f=fopen(argv[1],"rb"); if(!f) return 3;
  unsigned char rope[73728]; if(fread(rope,1,sizeof rope,f)!=sizeof rope) return 4; fclose(f);
  cpu_reset(); set_fixed(rope);
  FILE *in=fopen(argv[2],"r"); if(!in) return 5;
  unsigned end, tick, ch, val; if(fscanf(in,"%u",&end)!=1) return 6;
  int has=fscanf(in,"%u %u %u",&tick,&ch,&val)==3;
  for(unsigned i=0;i<end;i++) {
    if(has && i==tick) {
      int ok=packet_write(ch,val);
      printf("{\"ev\":\"input\",\"cycle\":%u,\"ch\":%u,\"val\":%u,\"accepted\":%d}\n",i,ch,val,ok);
      if(ok<=0) return 7;
      has=fscanf(in,"%u %u %u",&tick,&ch,&val)==3;
    }
    cpu_step(1);
    unsigned z=(uint16_t)State.Erasable[0][5], fb=((uint16_t)State.Erasable[0][4])>>10;
    if((fb==032 && z==02776)||(fb==004 && (z==03254||z==03270||z==03261||z==03267))||(fb==014 && z==03135))
      printf("{\"ev\":\"checkpoint\",\"cycle\":%u,\"z\":%u,\"bank\":%u,\"flagword3\":%u,\"imodes30\":%u,\"modreg\":%u}\n",i+1,z,fb,(uint16_t)State.Erasable[0][077],(uint16_t)State.Erasable[2][0102],(uint16_t)State.Erasable[2][011]);
    for(int j=0;j<8;j++) mix((uint16_t)State.Erasable[0][j]);
    uint32_t p; while((p=packet_read())) printf("{\"ev\":\"output\",\"cycle\":%u,\"ch\":%u,\"val\":%u}\n",i+1,p>>16,p&32767);
    if((i+1)%10000==0 || i+1==end) {
      uint32_t ram=2166136261u;
      for(int b=0;b<8;b++) for(int j=0;j<256;j++) { uint16_t w=State.Erasable[b][j]; ram=(ram^(w&255))*16777619u; ram=(ram^(w>>8))*16777619u; }
      printf("{\"ev\":\"trace\",\"cycle\":%u,\"registerHash\":%u,\"ramHash\":%u,\"z\":%u,\"fb\":%u,\"eb\":%u}\n",i+1,hash,ram,(uint16_t)State.Erasable[0][5],(uint16_t)State.Erasable[0][4],(uint16_t)State.Erasable[0][3]);
    }
  }
  fclose(in); return 0;
}