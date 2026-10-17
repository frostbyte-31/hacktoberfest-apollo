/* GPL-2.0-or-later. Synthetic instrument experiment; flight code unmodified. */
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
#include "agc_engine.h"
extern agc_t State;
extern void cpu_reset(void), set_fixed(unsigned char *), cpu_step(uint32_t);
extern int packet_write(uint16_t,uint16_t);
extern uint32_t packet_read(void);
static long position[3], sent[3];
static double angle[3];
static unsigned pending[3];
static int direction[3];
static int key(char c) {
  if(c>='1' && c<='9') return c-'0';
  switch(c) {case '0':return 16;case 'V':return 17;case 'N':return 31;
  case 'E':return 28;case '+':return 26;case '-':return 27;case 'R':return 18;}
  return -1;
}
int main(int argc,char **argv) {
  if(argc!=4) return 2;
  FILE *f=fopen(argv[1],"rb"); if(!f) return 3;
  unsigned char rope[73728]; if(fread(rope,1,sizeof rope,f)!=sizeof rope)return 4; fclose(f);
  f=fopen(argv[2],"r"); if(!f)return 5;
  unsigned end,start,gap; char keys[256];
  if(fscanf(f,"%u %u %u %255s",&end,&start,&gap,keys)!=4)return 6; fclose(f);
  int feedback=strcmp(argv[3],"closed")==0;
  int actuator=strcmp(argv[3],"blocked")!=0;
  if(!feedback && strcmp(argv[3],"open")!=0 && actuator)return 7;
  cpu_reset(); set_fixed(rope);
  printf("{\"ev\":\"initial\",\"end\":%u,\"start\":%u,\"gap\":%u,\"keys\":\"%s\",\"feedback\":%d,\"position_counts\":[0,0,0],\"drive_count_degrees\":%.12f,\"sensor_count_degrees\":%.12f}\n",end,start,gap,keys,feedback,0.043948,360.0/32768);
  size_t next=0; unsigned old_checkpoint=0;
  for(unsigned t=0;t<end;t++) {
    if(next<strlen(keys) && t==start+next*gap) {
      int k=key(keys[next]); if(k<0)return 8;
      int ok=packet_write(015,k); if(ok<=0)return 9;
      printf("{\"ev\":\"crew\",\"cycle\":%u,\"key\":\"%c\",\"channel\":13,\"value\":%d,\"accepted\":%d}\n",t,keys[next],k,ok); next++;
    }
    /* One counter packet per cycle, preventing input-ringbuffer saturation.
       The upstream CDU FIFO supplies its own 6400-count/s fast-mode pacing. */
    if(feedback) for(int a=0;a<3;a++) if(pending[a]) {
      int op=direction[a]>0?021:023;
      int ok=packet_write(0200|(032+a),op); if(ok<=0)return 10;
      pending[a]--; sent[a]+=direction[a];
      printf("{\"ev\":\"sensor\",\"cycle\":%u,\"axis\":%d,\"channel\":%d,\"operation\":%d,\"accepted\":%d,\"sensor_position_counts\":%ld}\n",t,a,0200|(032+a),op,ok,sent[a]);
      break;
    }
    cpu_step(1);
    unsigned z=(uint16_t)State.Erasable[0][5];
    unsigned fb=((uint16_t)State.Erasable[0][4])>>10;
    unsigned checkpoint=fb==07 && (z==03073 || z==03110 || z==03636 || z==03637 || z==03706)?z:0;
    if(checkpoint && checkpoint!=old_checkpoint)
      printf("{\"ev\":\"checkpoint\",\"cycle\":%u,\"bank\":%u,\"z\":%u,\"a\":%u,\"target\":[%u,%u,%u],\"cdu\":[%u,%u,%u],\"imucadr\":%u}\n",t+1,fb,z,(uint16_t)State.Erasable[0][0],(uint16_t)State.Erasable[0][0321],(uint16_t)State.Erasable[0][0322],(uint16_t)State.Erasable[0][0323],(uint16_t)State.Erasable[0][032],(uint16_t)State.Erasable[0][033],(uint16_t)State.Erasable[0][034],(uint16_t)State.Erasable[2][0304]);
    old_checkpoint=checkpoint;
    uint32_t p;
    while((p=packet_read())) {
      int ch=p>>16,v=p&077777;
      printf("{\"ev\":\"output\",\"cycle\":%u,\"channel\":%d,\"value\":%d}\n",t+1,ch,v);
      if(ch>=0174 && ch<=0176 && (State.InputChannel[012]&010) && !(State.InputChannel[012]&020)) {
        int a=ch-0174,sgn=(v&040000)?-1:1,n=v&037777;
        if(!actuator) {
          printf("{\"ev\":\"blocked\",\"cycle\":%u,\"axis\":%d,\"drive_pulses\":%d}\n",t+1,a,sgn*n);
          continue;
        }
        if(pending[a] && direction[a]!=sgn)return 11;
        angle[a]+=sgn*n*0.043948;
        long counts=(long)(angle[a]/(360.0/32768));
        long delta=counts-position[a];
        pending[a]+=(unsigned)labs(delta); position[a]=counts; direction[a]=sgn;
        printf("{\"ev\":\"plant\",\"cycle\":%u,\"axis\":%d,\"drive_pulses\":%d,\"position_counts\":%ld,\"angle_degrees\":%.12f,\"enable12\":%d}\n",t+1,a,sgn*n,position[a],angle[a],State.InputChannel[012]);
      }
    }
    if((t+1)%10000==0 || t+1==end) {
      printf("{\"ev\":\"sample\",\"cycle\":%u,\"position_counts\":[%ld,%ld,%ld],\"sent\":[%ld,%ld,%ld],\"pending\":[%u,%u,%u],\"cdu\":[%u,%u,%u],\"chan12\":%u,\"failreg\":[%u,%u,%u]}\n",t+1,position[0],position[1],position[2],sent[0],sent[1],sent[2],pending[0],pending[1],pending[2],(uint16_t)State.Erasable[0][032],(uint16_t)State.Erasable[0][033],(uint16_t)State.Erasable[0][034],State.InputChannel[012],(uint16_t)State.Erasable[0][0375],(uint16_t)State.Erasable[0][0376],(uint16_t)State.Erasable[0][0377]);
    }
  }
  return next==strlen(keys)?0:12;
}