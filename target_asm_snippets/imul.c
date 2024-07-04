#include <stdint.h>
#include <stdio.h>

#define MUL_ITERATIONS 100000

int main() {
	uint32_t performed = 0;
	uint32_t operand1 = 0x80000;
	uint32_t operand2 = 0x4;
	uint32_t faulty_result_found = 0;

	#pragma GCC unroll 10
	while (performed++ < MUL_ITERATIONS) {
		__asm__ volatile (
			"movl %[op1], %%eax;\n\t"
			"imull %[op2], %%eax;\n\t"
			"movl %[op1], %%ebx;\n\t"
			"imull %[op2], %%ebx;\n\t"
			"xor %%ecx, %%ecx;\n\t"
			"cmp %%eax, %%ebx;\n\t"
			"setne %%cl;\n\t"
			"addl %%ecx, %[faulty_result]\n\t"

			: [faulty_result] "+r" (faulty_result_found)	// Output operands
			: [op1] "r" (operand1), [op2] "r" (operand2)	// Input operands
			: "%eax", "%ebx", "%ecx"
								// Clobbered register
		);
	}

	// __asm__ volatile (
	// 	"movl $100000, %%ecx\n\t"
	// 	"head:\n\t"
	// 	"movl %[op1], %%eax;\n\t"
	// 	"imull %[op2], %%eax;\n\t"
	// 	"movl %[op1], %%ebx;\n\t"
	// 	"imull %[op2], %%ebx;\n\t"
	// 	"cmp %%eax, %%ebx;\n\t"
	// 	"setne %%al;\n\t"
	// 	"movzx %%al, %%eax;\n\t"
	// 	"addl %%eax , %[faulty_result]\n\t"
	// 	"decl %%ecx\n\t"
	// 	"jnz head\n\t"
	// 	: [faulty_result] "+r" (faulty_result_found)	// Output operands
	// 	: [op1] "r" (operand1), [op2] "r" (operand2)	// Input operands
	// 	: "%eax", "%ebx", "%ecx"						// Clobbered register
	// );

	printf("Result: 0x%x\n", faulty_result_found);
	return 0;
}