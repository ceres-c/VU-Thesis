#include "glitch.h"

glitch_t glitch = {0, 0, {TPS_REG_BUCK2CTRL, TPS_VCORE_MAX}, {TPS_REG_BUCK2CTRL, TPS_VCORE_MIN}, {TPS_REG_BUCK2CTRL, TPS_VCORE_MAX}};

#define UART_HW_NO_INPUT 0x100
#define ESTIMATE_ROUNDS 100
#define PICO_UART_RX_TIME 84	// Time in us between UART data appearing on the channel and it
								// being available to the Pico RX FIFO (measured externally)

inline static void uart_hw_write(uint8_t data) {
	UART_TARGET_PTR->dr = data;
}
inline static volatile uint8_t uart_hw_read(void) {
	return UART_TARGET_PTR->dr;
}
inline static volatile bool uart_hw_readable(void) {
	return !(UART_TARGET_PTR->fr & UART_UARTFR_RXFE_BITS);
}
inline static volatile uint8_t uart_hw_read_blocking(void) {
	while (!uart_hw_readable())
		tight_loop_contents();
	return uart_hw_read();
}
inline static volatile uint16_t uart_hw_read_timeout_cycles(uint32_t timeout_cycles) {
	for (uint32_t i = 0; i < timeout_cycles; i++) {
		if (uart_hw_readable())
			return uart_hw_read();
	}
	return UART_HW_NO_INPUT;
}
static void uart_hw_readu32(readu32_t *r) {
	r->valid = false;
	uint16_t c1 = uart_hw_read_timeout_cycles(READ_TIMEOUT_CYCLES);
	uint16_t c2 = uart_hw_read_timeout_cycles(READ_TIMEOUT_CYCLES);
	uint16_t c3 = uart_hw_read_timeout_cycles(READ_TIMEOUT_CYCLES);
	uint16_t c4 = uart_hw_read_timeout_cycles(READ_TIMEOUT_CYCLES);
	if (c1 == UART_HW_NO_INPUT || c2 == UART_HW_NO_INPUT || c3 == UART_HW_NO_INPUT || c4 == UART_HW_NO_INPUT) {
		return;
	}
	r->valid = true;
	r->val = ((c4 & 0xFF) << 24) | ((c3 & 0xFF) << 16) | ((c2 & 0xFF) << 8) | (c1 & 0xFF);
	return;
}

void target_uart_init(void) {
	uart_init(UART_TARGET, UART_TARGET_BAUD);

	uart_set_hw_flow(UART_TARGET, false, false);
	uart_set_format(UART_TARGET, UART_TARGET_DATA_BITS, UART_TARGET_STOP_BITS, UART_TARGET_PARITY);
	uart_set_fifo_enabled(UART_TARGET, false); // Char by char

	if (uart_is_readable_within_us(UART_TARGET, 100)) // Drain buffer
		uart_getc(UART_TARGET);

	uart_level_shifter_enable();
}

static void sort(uint32_t *arr, int n) {
	/*
	 * Simple bubble sort implementation to sort an array of uint32_t values.
	 * Good enough to calculate the median of a small array.
	 */
	for (int i = 0; i < n; i++) {
		for (int j = i + 1; j < n; j++) {
			if (arr[i] > arr[j]) {
				uint32_t temp = arr[i];
				arr[i] = arr[j];
				arr[j] = temp;
			}
		}
	}
}

bool ping_target(uint target_count) {
	/*
	 * Counts the number of received `R` characters and compares to a fixed number that has been
	 * verified to be sufficient to guarantee the board is actually running smoothly (not hanging
	 * right after a reboot) and VCore is stable.
	 *
	 * Arguments:
	 *	- target_count: the number of `R` characters to expect
	 */

	while(uart_hw_readable()) { // Drain buffer
		volatile uint8_t data = uart_hw_read();
	}

	uint32_t th = timer_hw->timerawh;
	uint32_t tl = timer_hw->timerawl;
	th += tl + TARGET_REACHABLE_US < tl;
	tl += TARGET_REACHABLE_US;
	uint32_t count = 0;
	do {
		if (uart_hw_readable()) {
			if (uart_hw_read() == T_CMD_READY) {
				count++;
			}
		}
	} while ((timer_hw->timerawh < th || timer_hw->timerawl < tl) && count < target_count);
	return count >= target_count;
}

void uart_echo(void) {
	puts("UART echo, power cycle to exit");
	while (true) {
		int c = getchar_timeout_us(0);
		if (c != PICO_ERROR_TIMEOUT) {
			uart_hw_write(c);
		}
		if (uart_hw_readable()) {
			putchar(uart_hw_read());
		}
	}
}

bool glitcher_arm(uint8_t expected_ints) {
	/*
	 * Performs a glitch with the current glitch parameters and checks the target response.
	 *
	 * Arguments:
	 *	- expected_ints: the number of uint32_t values expected to be received from the target (max 10)
	 */
	volatile uint8_t data;
	uint32_t th, tl;
	readu32_t rets[10];
	int write_prep_res = PICO_ERROR_GENERIC, write_glitch_res = PICO_ERROR_GENERIC, write_restore_res = PICO_ERROR_GENERIC;

	if (expected_ints > 10) {
		return false;
	}

	data = uart_hw_read(); // Clear the RX FIFO

	// Wait for trigger
	th = timer_hw->timerawh;
	tl = timer_hw->timerawl;
	th += tl + TARGET_REACHABLE_US < tl;
	tl += TARGET_REACHABLE_US;
	do {
		if (uart_hw_readable()) {
			if (uart_hw_read() == T_CMD_READY) goto triggered;
		}
	} while (timer_hw->timerawh < th || timer_hw->timerawl < tl);
	putchar(P_CMD_RESULT_UNREACHABLE);
	return false;

	triggered:
	write_prep_res = i2c_write_timeout_us(I2C_PMBUS, PMBUS_PMIC_ADDRESS, glitch.cmd_prep, TPS_WRITE_REG_CMD_LEN, false, 100);
	busy_wait_us_32(glitch.ext_offset);
	write_glitch_res = i2c_write_timeout_us(I2C_PMBUS, PMBUS_PMIC_ADDRESS, glitch.cmd_glitch, TPS_WRITE_REG_CMD_LEN, false, 100);
	busy_wait_us_32(glitch.width);
	write_restore_res = i2c_write_timeout_us(I2C_PMBUS, PMBUS_PMIC_ADDRESS, glitch.cmd_restore, TPS_WRITE_REG_CMD_LEN, false, 100);

	if (write_prep_res != TPS_WRITE_REG_CMD_LEN | write_glitch_res != TPS_WRITE_REG_CMD_LEN || write_restore_res != TPS_WRITE_REG_CMD_LEN) {
		putchar(P_CMD_RESULT_PMIC_FAIL);
		return false;
	}

	// Check if target is still alive
	th = timer_hw->timerawh;
	tl = timer_hw->timerawl;
	th += tl + TARGET_REACHABLE_US < tl;
	tl += TARGET_REACHABLE_US;
	do {
		if (uart_hw_readable()) goto alive;
	} while (timer_hw->timerawh < th || timer_hw->timerawl < tl);
	putchar(P_CMD_RESULT_RESET);
	return false;

	alive:
	data = uart_hw_read();
	switch (data) {
	case T_CMD_DONE:
		// done with target code, retrieve results
		for (uint8_t i = 0; i < expected_ints; i++) { // First read all the results
			uart_hw_readu32(&rets[i]);
			if (!rets[i].valid) {
				putchar(P_CMD_RESULT_DATA_TIMEOUT);
				return false;
			}
		}
		putchar(P_CMD_RESULT_ALIVE); // Since we got all the results, the target is alive
		for (uint8_t i = 0; i < expected_ints; i++) {
			putu32(rets[i].val);
		}
		break;
	case T_CMD_ANSI_ESC:
		// target is sending some crash debug info, probably.
		th = timer_hw->timerawh;
		tl = timer_hw->timerawl;
		th += tl + CRASH_INFO_TIMEOUT_US < tl;
		tl += CRASH_INFO_TIMEOUT_US;
		putchar(P_CMD_RESULT_ANSI_CTRL_CODE);
		while (timer_hw->timerawh < th || timer_hw->timerawl < tl) {
			// Sometimes the target will start dumping the whole ram, so we need to timeout or we'll get stuck here
			putchar(data);
			if (!uart_is_readable_within_us(UART_TARGET, 1000)) break;
			data = uart_hw_read();
		}
	case T_CMD_READY:
		// ready -> target reset? Why no done?
		// fallback
	default:
		putchar(P_CMD_RESULT_ZOMBIE);
		putchar(data);
		break;
	}
	return true;
}

int measure_loop(void) {
	/*
	 * This function gives a rough estimate for the glitch offset parameter.
	 * It takes into account:
	 *  - The time length of the fixed loop in the target firmware that happens
	 *    after the byte `T_CMD_READY` is sent by the target.
	 *  - The reaction time of the pico to data on the UART channel (time between
	 *    the data being on the channel and it being available to the Pico RX FIFO).
	 *
	 * It does not consider the time at the target between writing to the UART
	 * TX FIFO and the data appearing on the channel. This means that  the interesting
	 * offset will be slightly smaller than the one estimated by this function.
	 *
	 * Returns:
	 *  - >0: the estimated offset in us
	 *  - -1: target is unreachable
	 *  - -2: measured time without the loop is greater or equal to the standard time,
	 *        can't estimate the duration of the wait loop on the target
	 *  - -3: offset added by the loop is smaller than PICO_RX_TIME
	 */
	uint32_t th, tl;
	volatile uint8_t data; // Used to flush the RX FIFO
	uint32_t measurements[ESTIMATE_ROUNDS];
	uint32_t loop_duration = 0;

	while(uart_hw_readable()) { // Drain buffer
		data = uart_hw_read();
	}

	// Calculate median time between two resets in standard conditions
	uint32_t t1 = 0, t2= 0;
	for (int i = 0; i < ESTIMATE_ROUNDS; i++) {
		// Wait for connection init from target

		th = timer_hw->timerawh;
		tl = timer_hw->timerawl;
		th += tl + TARGET_REACHABLE_US < tl;
		tl += TARGET_REACHABLE_US;
		do {
			if (uart_hw_readable()) {
				if (uart_hw_read() == T_CMD_READY) goto reachable;
			}
		} while (timer_hw->timerawh < th || timer_hw->timerawl < tl);
		return -1;

		reachable:
		t1 = time_us_32();
		data = uart_hw_read();
		// Don't send anything, now the target will wait for timeout and then reset

		th = timer_hw->timerawh;
		tl = timer_hw->timerawl;
		th += tl + TARGET_REACHABLE_US < tl;
		tl += TARGET_REACHABLE_US;
		do {
			if (uart_hw_readable()) {
				if (uart_hw_read() == T_CMD_DONE) goto done;
			}
		} while (timer_hw->timerawh < th || timer_hw->timerawl < tl);
		return -1;

		done:
		t2 = time_us_32();
		data = uart_hw_read();

		measurements[i] = t2 - t1;
	}
	sort(measurements, ESTIMATE_ROUNDS);
	return measurements[ESTIMATE_ROUNDS / 2] - PICO_UART_RX_TIME;
}

bool __no_inline_not_in_flash_func(uart_debug_pin_toggle)(void) {
	/*
	 * This function can be used to measure (externally) the time between the data
	 * being on the UART channel, and it being available to the Pico.
	 */
	volatile uint8_t data = uart_hw_read(); // Start off with a clean RX data register

	uint32_t th = timer_hw->timerawh;
	uint32_t tl = timer_hw->timerawl;
	th += tl + TARGET_REACHABLE_US < tl;
	tl += TARGET_REACHABLE_US;
	do {
		if (uart_hw_readable()) goto toggle;
	} while (timer_hw->timerawh < th || timer_hw->timerawl < tl);
	return false;

	toggle:
	gpio_xor_mask(PIN_DEBUG_MASK);
	return true;
}
