/* steady state M/G/N+G queue with ring time and after call work.
   spec file:
     seed S | narr K | warm F | timeout T | slt 20 | ghost 10 | nrange a b
     stream rate patience_file ring_file talk_file after_file
   prints per N: N sl ab ans_frac(all) ans_frac(stream0) ans_frac(stream1) ... */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#include <math.h>

typedef struct { double *v; long n; } arr;
typedef struct { double rate; arr pat, ring, talk, after; } stream;

static uint64_t st;
static inline uint64_t nx(void){ uint64_t z=(st+=0x9E3779B97F4A7C15ULL); z=(z^(z>>30))*0xBF58476D1CE4E5B9ULL; z=(z^(z>>27))*0x94D049BB133111EBULL; return z^(z>>31);}
static inline double u01(void){ return (nx()>>11)*(1.0/9007199254740992.0);}
static inline double pick(arr *a){ return a->v[(long)(u01()*a->n)]; }

static arr load(const char *fn){
  arr a={0,0}; long cap=1024; a.v=malloc(cap*sizeof(double));
  FILE *f=fopen(fn,"r"); if(!f){fprintf(stderr,"cannot open %s\n",fn);exit(2);}
  double x; while(fscanf(f,"%lf",&x)==1){ if(a.n==cap){cap*=2;a.v=realloc(a.v,cap*sizeof(double));} a.v[a.n++]=x; }
  fclose(f); if(!a.n){fprintf(stderr,"empty %s\n",fn);exit(2);} return a;
}

int main(int argc,char**argv){
  if(argc<2){fprintf(stderr,"usage: qsim spec\n");return 2;}
  FILE *f=fopen(argv[1],"r"); if(!f){perror("spec");return 2;}
  uint64_t seed=1; long narr=100000; double warm=0.05, timeout=0, slt=20, ghost=10; int na=1,nb=1;
  stream S[8]; int ns=0; char key[64];
  while(fscanf(f,"%63s",key)==1){
    if(!strcmp(key,"seed")) fscanf(f,"%lu",&seed);
    else if(!strcmp(key,"narr")) fscanf(f,"%ld",&narr);
    else if(!strcmp(key,"warm")) fscanf(f,"%lf",&warm);
    else if(!strcmp(key,"timeout")) fscanf(f,"%lf",&timeout);
    else if(!strcmp(key,"slt")) fscanf(f,"%lf",&slt);
    else if(!strcmp(key,"ghost")) fscanf(f,"%lf",&ghost);
    else if(!strcmp(key,"nrange")) fscanf(f,"%d %d",&na,&nb);
    else if(!strcmp(key,"stream")){
      char p[512],r[512],t[512],a[512]; double rate;
      fscanf(f,"%lf %511s %511s %511s %511s",&rate,p,r,t,a);
      S[ns].rate=rate; S[ns].pat=load(p); S[ns].ring=load(r); S[ns].talk=load(t); S[ns].after=load(a); ns++;
    }
  }
  fclose(f);
  double tot=0; for(int i=0;i<ns;i++) tot+=S[i].rate;
  double *fr=malloc(sizeof(double)*(nb+2));
  for(int N=na;N<=nb;N++){
    st=seed;
    double *free_t=calloc(N,sizeof(double));
    double t=0; long wstart=(long)(warm*narr);
    long ent=0, ans=0, ans20=0, abn=0, tmo=0; long sent[8]={0}, sans[8]={0};
    for(long i=0;i<narr;i++){
      t += -log(1.0-u01())/tot;
      double x=u01()*tot; int k=0; while(k<ns-1 && x>=S[k].rate){x-=S[k].rate;k++;}
      double p=pick(&S[k].pat), r=pick(&S[k].ring), tk=pick(&S[k].talk), af=pick(&S[k].after);
      int m=0; for(int j=1;j<N;j++) if(free_t[j]<free_t[m]) m=j;
      double s = free_t[m] > t ? free_t[m] : t;
      double w = s - t;
      int rec = i>=wstart;
      if(rec){ent++; sent[k]++;}
      if(timeout>0 && w>=timeout && p>timeout){ if(rec) tmo++; continue; }
      if(p<=w){ if(rec && p>=ghost) abn++; continue; }
      if(timeout>0 && w+r>=timeout && p>timeout){ free_t[m]=t+timeout; if(rec) tmo++; continue; }
      if(p<=w+r){ free_t[m]=t+p; if(rec && p>=ghost) abn++; continue; }
      free_t[m]=s+r+tk+af;
      if(rec){ ans++; sans[k]++; if(w+r<=slt) ans20++; }
    }
    double den=(double)(ans+abn+tmo);
    printf("%d %.6f %.6f %.6f",N, den>0?ans20/den:1.0, ent?(double)abn/ent:0.0, ent?(double)ans/ent:0.0);
    for(int k=0;k<ns;k++) printf(" %.6f", sent[k]?(double)sans[k]/sent[k]:0.0);
    printf("\n");
    free(free_t);
  }
  return 0;
}
