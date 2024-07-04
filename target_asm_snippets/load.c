#include <stdint.h>
#include <stdio.h>

#define MUL_ITERATIONS 100000

int main() {
	uint32_t stack_storage = 0xAAAAAAAA; // 10101010...
	uint32_t wrong_value = 0;
	uint32_t faulty_result_found = 0;

	__asm__ volatile (
		"movl %[stack_mem], %%eax;\n\t"
		"xorl %%ecx, %%ecx;\n\t" // i = 0

		"head:\n\t"
		"movl %[stack_mem], %%ebx;\n\t"
		"cmp %%eax, %%ebx;\n\t"
		"cmovne %%ebx, %[wrong]\n\t"
		"setne %%bl;\n\t" // Can now overwrite %ebx, as we've already copied the value to %[wrong]
		"movzx %%bl, %%ebx;\n\t"
		"addl %%ebx , %[faulty_result]\n\t"
		"movl %[stack_mem], %%ebx;\n\t"
		"cmp %%eax, %%ebx;\n\t"
		"cmovne %%ebx, %[wrong]\n\t"
		"setne %%bl;\n\t"
		"movzx %%bl, %%ebx;\n\t"
		"addl %%ebx , %[faulty_result]\n\t"

		// loop with registers
		"inc %%ecx;\n\t"
		"cmp $10, %%ecx;\n\t"
		"jnz head\n\t"

		: [faulty_result] "+r" (faulty_result_found),	// Output operands
			[wrong] "+r" (wrong_value)
		: [stack_mem] "m" (stack_storage)
		: "%eax",	// Reference value of stack_storage
			"%ebx",	// Scratch
			"%ecx"	// i
	);

	printf("Result: 0x%x\n", faulty_result_found);
	printf("Wrong value: 0x%x\n", wrong_value);
	return 0;
}