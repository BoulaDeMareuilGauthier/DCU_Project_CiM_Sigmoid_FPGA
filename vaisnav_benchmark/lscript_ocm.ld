/*
 * Minimal OCM-only linker script for DDR init helper.
 * Everything at 0x0 - 0x30000 (192 KB on-chip RAM).
 * No MMU, no DDR dependency.
 */
_STACK_SIZE = 0x1000;
_HEAP_SIZE  = 0x1000;

MEMORY
{
   ps7_ram_0 : ORIGIN = 0x0, LENGTH = 0x30000
}

ENTRY(_start)

SECTIONS
{
.text : {
   *(.boot)
   *(.text)
   *(.text.*)
} > ps7_ram_0

.rodata : {
   *(.rodata)
   *(.rodata.*)
} > ps7_ram_0

.data : {
   __data_start = .;
   *(.data)
   *(.data.*)
   __data_end = .;
} > ps7_ram_0

.bss (NOLOAD) : {
   __bss_start = .;
   *(.bss)
   *(.bss.*)
   *(COMMON)
   __bss_end = .;
} > ps7_ram_0

.heap (NOLOAD) : {
   . = ALIGN(16);
   _heap = .;
   . += _HEAP_SIZE;
   _heap_end = .;
} > ps7_ram_0

.stack (NOLOAD) : {
   . = ALIGN(16);
   _stack_end = .;
   . += _STACK_SIZE;
   . = ALIGN(16);
   _stack = .;
   __stack = _stack;
} > ps7_ram_0

end = .;
}
