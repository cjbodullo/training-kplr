#include <stdio.h>
#include <stdlib.h>
#include <string.h>
int main(int argc,char**argv){
    size_t n = argc>1?atoll(argv[1]):1000000;
    char *buf = malloc(n);
    memset(buf,'a',n);
    unsigned long h=0;
    for(size_t i=0;i<n;i++) h = h*1315423911u + (unsigned char)buf[i];
    printf("%lu\n", h);
    return 0;
}
