/* GPL-2.0-or-later. Read-only Phase 8 observer around the pinned AGC.
 * Stimuli are original Phase 5 packets plus normal channel-015 DSKY keys.
 * No assignments to flight erasable memory, emulator instructions or channels.
 */
#include <stdio.h>
#include <stdint.h>
#include "agc_engine.h"
extern agc_t State;
extern void cpu_reset(void),set_fixed(unsigned char *),cpu_step(uint32_t);
extern int packet_write(uint16_t,uint16_t);
extern uint32_t packet_read(void);
static unsigned ram(unsigned a) {return (uint16_t)State.Erasable[a/0400][a%0400];}
static void sample(const char *event,unsigned tick) {
 printf("{\"ev\":\"%s\",\"cycle\":%u,\"modreg\":%u,\"imodes30\":%u,\"imodes33\":%u,\"thrust\":%u,\"chan12\":%u,\"chan14\":%u,\"chan30\":%u,\"chan31\":%u,\"failreg\":[%u,%u,%u],\"cdu\":[%u,%u,%u],\"state\":[",event,tick,ram(01011),ram(01302),ram(01303),ram(055),State.InputChannel[012],State.InputChannel[014],State.InputChannel[030],State.InputChannel[031],ram(0375),ram(0376),ram(0377),ram(032),ram(033),ram(034));
 for(unsigned a=074;a<0114;a++) printf("%s%u",a==074?"":",",ram(a));
 printf("]}\n");
}
int main(int argc,char **argv) {
 if(argc!=4)return 2;
 FILE *f=fopen(argv[1],"rb");if(!f)return 3;
 unsigned char rope[73728];if(fread(rope,1,sizeof rope,f)!=sizeof rope)return 4;
 fclose(f);f=fopen(argv[2],"r");if(!f)return 5;
 unsigned end,tick,ch,val;if(fscanf(f,"%u",&end)!=1)return 6;
 int has=fscanf(f,"%u %u %u",&tick,&ch,&val)==3;
 FILE *points=fopen(argv[3],"r");if(!points)return 11;
 unsigned banks[512],zs[512],npoints=0;
 while(npoints<512 && fscanf(points,"%o %o",&banks[npoints],&zs[npoints])==2)npoints++;
 fclose(points);
 cpu_reset();set_fixed(rope);
 printf("{\"ev\":\"initial\",\"cycles\":%u,\"ram_writes\":0,\"vehicle_model\":false,\"source\":\"pinned ringbuffer AGC\"}\n",end);
 sample("state",0);
 unsigned prior[25];
 for(unsigned i=0;i<16;i++)prior[i]=ram(074+i);
 unsigned addresses[]={01011,01302,01303,055,0375,0376,0377};
 for(unsigned i=0;i<7;i++)prior[16+i]=ram(addresses[i]);
 prior[23]=State.InputChannel[012];prior[24]=State.InputChannel[014];
 for(unsigned t=0;t<end;t++) {
  if(has && tick<t)return 9;
  while(has && tick==t) {
   if(ch&0200)return 10; /* No fabricated counter-operation feedback. */
   int ok=packet_write(ch,val);
   printf("{\"ev\":\"input\",\"cycle\":%u,\"channel\":%u,\"value\":%u,\"accepted\":%d}\n",t,ch,val,ok);
   if(ok<=0)return 7;
   has=fscanf(f,"%u %u %u",&tick,&ch,&val)==3;
  }
  unsigned bank=ram(4)>>10,z=ram(5);
  for(unsigned i=0;i<npoints;i++)if(bank==banks[i] && z==zs[i]) {
   printf("{\"ev\":\"before\",\"cycle\":%u,\"bank\":%u,\"z\":%u,\"a\":%u,\"l\":%u,\"q\":%u,\"eb\":%u,\"thrust\":%u,\"flagword3\":%u,\"modreg\":%u}\n",t,bank,z,ram(0),ram(1),ram(2),ram(3),ram(055),ram(077),ram(01011));
   break;
  }
  cpu_step(1);
  uint32_t p;while((p=packet_read()))printf("{\"ev\":\"output\",\"cycle\":%u,\"channel\":%u,\"value\":%u}\n",t+1,p>>16,p&077777);
  unsigned now[25];int changed=0;
  for(unsigned i=0;i<16;i++)now[i]=ram(074+i);
  for(unsigned i=0;i<7;i++)now[16+i]=ram(addresses[i]);
  now[23]=State.InputChannel[012];now[24]=State.InputChannel[014];
  for(unsigned i=0;i<25;i++){if(now[i]!=prior[i])changed=1;prior[i]=now[i];}
  if(changed)sample("state",t+1);
  if((t+1)%10000==0 || t+1==end)sample("sample",t+1);
 }
 fclose(f);return has?8:0;
}
