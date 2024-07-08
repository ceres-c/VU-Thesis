#include <stdint.h>
#include <stdio.h>

#define REP10(BODY) \
		BODY BODY BODY BODY BODY BODY BODY BODY BODY BODY
#define CODE_BODY \
	"movl %[op1], %%eax;\n\t" \
	"imull %[op2], %%eax;\n\t" \
	"movl %[op1], %%ebx;\n\t" \
	"imull %[op2], %%ebx;\n\t" \
	"xor %%ecx, %%ecx;\n\t" \
	"cmp %%eax, %%ebx;\n\t" \
	"setne %%cl;\n\t" \
	"addl %%ecx, %[fault_count]\n\t"

int main() {

		uint32_t operand1 = 0x80000, operand2 = 0x4; // Taken from plundervolt paper // TODO add command to change these
		uint32_t result_a = 0, result_b = 0;
		uint32_t fault_count = 0;

		__asm__ volatile (
			// REP100(REP100(CODE_BODY))
			// REP100(REP100(CODE_BODY))
			// REP100(REP100(CODE_BODY))
			REP10(CODE_BODY)

			: [fault_count] "+r" (fault_count)			// Output operands
			: [op1] "r" (operand1), [op2] "r" (operand2)	// Input operands
			: "%eax", "%ebx", "%ecx"						// Clobbered register
		);

	printf("Result: 0x%x\n", fault_count);
	return 0;
}