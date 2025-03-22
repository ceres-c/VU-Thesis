#ifndef _GLITCH_H
#define _GLITCH_H

#include "pico/error.h"
#include "picocoder.h"
#include "cmd.h"
#include "pmbus.h"

#define READ_TIMEOUT_CYCLES			5000 // At the standard 125MHz, this is 8ns*5000 = 40us (plus loop overhead)
#define CRASH_INFO_TIMEOUT_US		1000000 // Receive crash info for 1s max
#define TARGET_REACHABLE_US			9000 // The target sends a `R` every ~3-7,5ms, if after 9ms we haven't seen it, it's dead
#define VOLT_TEST_TIMEOUT_US		6000 // 6ms timeout to receive all bytes in a voltage test (it normally takes ~5ms)
#define PING_VCORE_STABLE_TIME_US	350000
#define PING_VCORE_STABLE_CHARS		5
#define PING_VCORE_STABLE_CHARS_SLOW	1 // With ucode updates, it can take up to 6,6 us per cycle

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
bool ping_target(uint target_count);
void uart_echo(void);
bool glitcher_arm(uint8_t expected_ints);
int measure_loop(void);
bool uart_debug_pin_toggle(void);

static inline void uart_level_shifter_enable(void) {
	*SET_GPIO_ATOMIC = 1 << PIN_UART_OE;
}
static inline void uart_level_shifter_disable(void) {
	*CLR_GPIO_ATOMIC = 1 << PIN_UART_OE;
}

#endif // _GLITCH_H
