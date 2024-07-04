#include <stdint.h>
#include <stdio.h>

#define MUL_ITERATIONS 100000

int main() {
	uint32_t stack_storage = 0xAAAAAAAA; // 10101010...
	uint32_t fault_count = 0;

	__asm__ volatile (
		"movl %[stack_mem], %%eax;\n\t"
		"movl %[stack_mem], %%ebx;\n\t"
		"xorl %%ecx, %%ecx;\n\t" // i = 0

		"head:\n\t"
		"cmp %%eax, %%ebx;\n\t"
		"setne %%dl;\n\t"
		"movzx %%dl, %%edx;\n\t"
		"addl %%edx , %[faulty_result]\n\t"

		// loop with registers
		"inc %%ecx;\n\t"
		"cmp $10, %%ecx;\n\t"
		"jnz head\n\t"

		: [faulty_result] "+r" (fault_count)	// Output operands
		: [stack_mem] "m" (stack_storage)
		: "%eax",	// Copy a of stack_storage
		  "%ebx",	// Copy b of stack_storage
		  "%ecx",	// i
		  "%edx"	// Scratch
	);

	printf("Result: 0x%x\n", fault_count);
	return 0;
}