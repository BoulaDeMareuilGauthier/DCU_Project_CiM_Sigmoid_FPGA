    .globl _start
_start:
    mrc p15,0,r0,c1,c0,0
    bic r0,r0,#0x1
    mcr p15,0,r0,c1,c0,0

    ldr sp,=__stack
    bl main
halt:
    b halt
    .end
