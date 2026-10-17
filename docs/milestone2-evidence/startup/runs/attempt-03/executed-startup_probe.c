/* GPL-2.0-or-later. Fresh-process, read-only Luminary 099 startup probe.
 * Only cpu_reset/set_fixed and packet_write initialize or stimulate the CPU.
 * All flight-state memory accesses below are reads. No vehicle model is used.
 */
#include <stdio.h>
#include <stdint.h>
#include "agc_engine.h"
extern agc_t State;
extern void cpu_reset(void), set_fixed(unsigned char *), cpu_step(uint32_t);
extern int packet_write(uint16_t, uint16_t);
extern uint32_t packet_read(void);
static unsigned ram(unsigned a) { return (uint16_t)State.Erasable[a/0400][a%0400]; }
static void sample(const char *event, unsigned t) {
 printf("{\"ev\":\"%s\",\"cycle\":%u,\"modreg\":%u,\"imodes30\":%u,\"imodes33\":%u,\"failreg\":[%u,%u,%u],\"chan30\":%u,\"chan31\":%u,\"chan12\":%u,\"cdu\":[%u,%u,%u]}\n", event,t,ram(01011),ram(01302),ram(01303),ram(0375),ram(0376),ram(0377),State.InputChannel[030],State.InputChannel[031],State.InputChannel[012],ram(032),ram(033),ram(034));
}
int main(int argc, char **argv) {
 if(argc!=3) return 2;
 FILE *f=fopen(argv[1],"rb"); if(!f) return 3;
 unsigned char rope[73728]; if(fread(rope,1,sizeof rope,f)!=sizeof rope) return 4;
 fclose(f); f=fopen(argv[2],"r"); if(!f) return 5;
 unsigned end,tick,ch,val; if(fscanf(f,"%u",&end)!=1) return 6;
 int has=fscanf(f,"%u %u %u",&tick,&ch,&val)==3;
 cpu_reset(); set_fixed(rope);
 printf("{\"ev\":\"initial\",\"cycles\":%u,\"ram_writes\":0,\"vehicle_model\":false,\"counter_packets\":0}\n",end);
 sample("state",0);
 unsigned prior[6]={ram(01011),ram(01302),ram(01303),ram(0375),ram(0376),ram(0377)};
 for(unsigned t=0;t<end;t++) {
  if(has && tick<t) return 9;
  while(has && tick==t) {
   if(ch&0200) return 10; /* No synthetic counter packets in startup experiment. */
   int ok=packet_write(ch,val);
   printf("{\"ev\":\"input\",\"cycle\":%u,\"channel\":%u,\"value\":%u,\"accepted\":%d}\n",t,ch,val,ok);
   if(ok<=0) return 7;
   has=fscanf(f,"%u %u %u",&tick,&ch,&val)==3;
  }
  unsigned bank=ram(4)>>10,z=ram(5);
  /* Verified against rope opcodes and retained Phase5 assembly excerpts. */
  if((bank==05 && (z==03002||z==03005||z==03054)) ||
     (bank==04 && (z==02043||z==02045||z==02065)) ||
     (bank==06 && (z==02321||z==02326||z==02327)) ||
     (bank==016 && z==02046)) {
   printf("{\"ev\":\"before\",\"cycle\":%u,\"bank\":%u,\"z\":%u,\"a\":%u,\"l\":%u,\"mpac5\":%u,\"phase_pairs\":[",t,bank,z,ram(0),ram(1),ram(0161));
   for(unsigned a=0752;a<=0765;a++) printf("%s%u",a==0752?"":",",ram(a));
   printf("],\"modreg\":%u,\"imodes30\":%u,\"imodes33\":%u}\n",ram(01011),ram(01302),ram(01303));
  }
  cpu_step(1);
  uint32_t p; while((p=packet_read())) printf("{\"ev\":\"output\",\"cycle\":%u,\"channel\":%u,\"value\":%u}\n",t+1,p>>16,p&077777);
  unsigned now[6]={ram(01011),ram(01302),ram(01303),ram(0375),ram(0376),ram(0377)};
  int changed=0; for(int i=0;i<6;i++) if(now[i]!=prior[i]) changed=1;
  if(changed) sample("state",t+1);
  for(int i=0;i<6;i++) prior[i]=now[i];
  if((t+1)%10000==0 || t+1==end) sample("sample",t+1);
 }
 fclose(f); return has?8:0;
}
