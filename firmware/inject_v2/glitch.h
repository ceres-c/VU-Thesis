#ifndef _GLITCH_H
#define _GLITCH_H

#include "picocoder.h"
#include "cmd.h"
#include "pmbus.h"

#define READ_TIMEOUT_CYCLES			5000 // At the standard 125MHz, this is 8ns*5000 = 40us (plus loop overhead)
#define TARGET_REACHABLE_US			7000 // The target sends a `R` every 3ms, if after 7ms we haven't seen it, it's dead
#define VOLT_TEST_TIMEOUT_US		6000 // 6ms timeout to receive all bytes in a voltage test (it normally takes ~5ms)
#define PING_VCORE_STABLE_TIME_US	350000
#define PING_VCORE_STABLE_CHARS		110

typedef struct glitch_s {
	uint32_t ext_offset;
	uint32_t width;
	uint8_t cmd_prep[TPS_WRITE_REG_CMD_LEN];
	uint8_t cmd_glitch[TPS_WRITE_REG_CMD_LEN];
	uint8_t cmd_restore[TPS_WRITE_REG_CMD_LEN];
} glitch_t;
extern glitch_t glitch;

typedef struct readu32_s {
	bool valid;
	uint32_t val;
} readu32_t;

void target_uart_init(void);
bool ping_target(void);
void uart_echo(void);
bool glitch_sync(void);
int estimate_offset(void);
bool uart_debug_pin_toggle(void);
int voltage_test(void);

static inline void uart_level_shifter_enable(void) {
	*SET_GPIO_ATOMIC = 1 << PIN_UART_OE;
}
static inline void uart_level_shifter_disable(void) {
	*CLR_GPIO_ATOMIC = 1 << PIN_UART_OE;
}
static inline bool glitcher_arm(void) { // TODO remove this function
	return glitch_sync();
}

#endif // _GLITCH_H
