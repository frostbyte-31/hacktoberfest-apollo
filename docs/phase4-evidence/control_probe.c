/* GPL-2.0-or-later. Read-only readiness instrumentation, not flight logic. */
#include <stdio.h>
#include <stdint.h>
#include "agc_engine.h"
extern agc_t State;
extern void cpu_reset(void),set_fixed(unsigned char*),cpu_step(uint32_t);
extern int packet_write(uint16_t,uint16_t);
extern uint32_t packet_read(void);
static unsigned ram(unsigned a){return (uint16_t)State.Erasable[a/0400][a%0400];}
int main(int argc,char **argv){
 if(argc!=3)return 2;
 FILE *f=fopen(argv[1],"rb"); if(!f)return 3;
 unsigned char rope[73728]; if(fread(rope,1,sizeof rope,f)!=sizeof rope)return 4; fclose(f);
 f=fopen(argv[2],"r");if(!f)return 5;
 unsigned end,tick,ch,val; if(fscanf(f,"%u",&end)!=1)return 6;
 int has=fscanf(f,"%u %u %u",&tick,&ch,&val)==3;
 cpu_reset();set_fixed(rope);
 printf("{\"ev\":\"initial\",\"cycles\":%u,\"chan30\":%u,\"chan31\":%u,\"chan32\":%u,\"chan33\":%u,\"ram_writes\":0}\n",end,State.InputChannel[030],State.InputChannel[031],State.InputChannel[032],State.InputChannel[033]);
 for(unsigned t=0;t<end;t++){
  if(has && tick==t){int ok=packet_write(ch,val);printf("{\"ev\":\"input\",\"cycle\":%u,\"channel\":%u,\"value\":%u,\"accepted\":%d}\n",t,ch,val,ok);if(ok<=0)return 7;has=fscanf(f,"%u %u %u",&tick,&ch,&val)==3;}
  cpu_step(1);
  unsigned z=ram(5),bank=ram(4)>>10;
  if(bank==016 && (z==02000||z==02041||z==02046||z==02163))
   printf("{\"ev\":\"checkpoint\",\"cycle\":%u,\"bank\":%u,\"z\":%u,\"a\":%u,\"chan30\":%u,\"chan31\":%u,\"imodes33\":%u,\"dapbools\":%u}\n",t+1,bank,z,ram(0),State.InputChannel[030],State.InputChannel[031],ram(01303),ram(0111));
  uint32_t p;while((p=packet_read()))printf("{\"ev\":\"output\",\"cycle\":%u,\"channel\":%u,\"value\":%u}\n",t+1,p>>16,p&077777);
  if((t+1)%10000==0 || t+1==end)
   printf("{\"ev\":\"sample\",\"cycle\":%u,\"modreg\":%u,\"chan30\":%u,\"chan31\":%u,\"imodes30\":%u,\"imodes33\":%u,\"dapbools\":%u,\"rcsflags\":%u,\"mass\":%u,\"lemmass\":%u,\"rhc_yaw\":%u,\"cdu\":[%u,%u,%u],\"failreg\":[%u,%u,%u]}\n",t+1,ram(01011),State.InputChannel[030],State.InputChannel[031],ram(01302),ram(01303),ram(0111),ram(01273),ram(01244),ram(01331),ram(043),ram(032),ram(033),ram(034),ram(0375),ram(0376),ram(0377));
 }
 fclose(f);return has?8:0;
}