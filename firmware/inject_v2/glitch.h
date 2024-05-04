#ifndef _GLITCH_H
#define _GLITCH_H

#include "picocoder.h"
#include "cmd.h"
#include "pmbus.h"

#define STDIO_NO_INPUT -2
#define READ_TIMEOUT_CYCLES 5000 // At the standard 125MHz, this is 8ns*5000 = 40us (plus loop overhead)

typedef enum {
	TARGET_IGNORE,		// Disarmed
	TARGET_UNKNOWN,		// Either disconnected or unknown state
	TARGET_READY,		// Target is connected and ready to be glitched
	TARGET_GLITCHED,	// Done the glitch
} target_state_t;
extern target_state_t target_state;

typedef struct glitch_s {
	uint32_t ext_offset;
	uint32_t width;
	uint8_t cmd_glitch[TPS_WRITE_REG_CMD_LEN];
	uint8_t cmd_restore[TPS_WRITE_REG_CMD_LEN];
} glitch_t;
extern glitch_t glitch;

void target_uart_init(void);
void uart_echo(void);

static inline void uart_level_shifter_enable(void) {
	*SET_GPIO_ATOMIC = 1 << PIN_UART_OE;
}
static inline void uart_level_shifter_disable(void) {
	*CLR_GPIO_ATOMIC = 1 << PIN_UART_OE;
}
static inline void glitcher_arm(void) {
	target_state = TARGET_UNKNOWN;
	uart_level_shifter_enable();
	uart_set_irq_enables(UART_TARGET, true, false);
}
static inline void glitcher_disarm(void) {
	uart_set_irq_enables(UART_TARGET, false, false);
	uart_level_shifter_disable();
	target_state = TARGET_IGNORE;
}

#endif // _GLITCH_H
