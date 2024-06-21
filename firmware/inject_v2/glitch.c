#include "glitch.h"

target_state_t target_state = TARGET_IGNORE;
glitch_t glitch = {0, 0, {TPS_REG_BUCK2CTRL, TPS_VCORE_SAFE}, {TPS_REG_BUCK2CTRL, TPS_VCORE_MIN}, {TPS_REG_BUCK2CTRL, TPS_VCORE_SAFE}};
uint8_t retval[4] = {0, 0, 0, 0};
uint8_t ret_i = 0;

#define UART_HW_NO_INPUT 0x100
#define ESTIMATE_ROUNDS 100
#define PICO_RX_TIME 85 // Time in us between UART data appearing on the channel and it
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

	target_state = TARGET_IGNORE;
	if (uart_is_readable_within_us(UART_TARGET, 100)) // Drain buffer
		uart_getc(UART_TARGET);

	uart_level_shifter_enable();
}

uint ping_target_count = 0;
void irq_ping_target_reboot_counter(void) {
	/* Registered as a UART IRQ, whenever an `R` is received it increments ping_target_count */
	volatile uint8_t d = uart_get_hw(UART_TARGET)->dr; // Clear the interrupt
	if (d == T_CMD_READY) {
		ping_target_count++;
	}
}
bool ping_target(void) {
	/*
	 * Counts the number of received `R` characters and compares to a fixed number that has been
	 * verified to be sufficient to guarantee the board is actually running smoothly (not hanging
	 * right after a reboot) and VCore is stable.
	 */
	bool ret = false;
	ping_target_count = 0;
	irq_set_exclusive_handler(UART0_IRQ, irq_ping_target_reboot_counter);

	volatile uint8_t data = uart_hw_read(); // Start off with a clean RX data register

	uint32_t th = timer_hw->timerawh; // TODO use this structure everywhere
	uint32_t tl = timer_hw->timerawl;
	th += tl + TARGET_REACHABLE_US < tl;
	tl += TARGET_REACHABLE_US;
	do {
		if (uart_hw_readable()) goto reachable;
	} while (timer_hw->timerawh < th || timer_hw->timerawl < tl);
	goto end;

	reachable:

	irq_set_enabled(UART0_IRQ, true);
	uart_set_irq_enables(UART_TARGET, true, false);

	for (int i = 0; i < PING_VCORE_STABLE_TIME_US / 3000; i++) {
		busy_wait_us_32(3000);
		if (ping_target_count >= PING_VCORE_STABLE_CHARS) {
			ret = true;
			break;
		}
	}

	end:
	uart_set_irq_enables(UART_TARGET, false, false);
	irq_set_enabled(UART0_IRQ, false);
	return ret;
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

bool glitch_sync(void) {
	volatile uint8_t data;
	uint32_t t;

	if (uart_is_readable_within_us(UART_TARGET, 100)) // Drain buffer
		uart_getc(UART_TARGET);

	// Connect to target
	t = time_us_32();
	do {
		if (uart_hw_readable()) goto reachable;
	} while ((time_us_32() - t) <= TARGET_REACHABLE_US);
	putchar(P_CMD_RESULT_UNREACHABLE);
	return false;

	reachable:
	data = uart_hw_read();
	if (data != T_CMD_READY) {
		putchar(P_CMD_RESULT_UNCONNECTABLE);
		return false;
	}
	uart_hw_write(T_CMD_CONNECT); // ACK connection

	// Wait for trigger
	t = time_us_32();
	do {
		if (uart_hw_readable()) goto triggered;
	} while ((time_us_32() - t) <= TARGET_REACHABLE_US);
	putchar(P_CMD_RESULT_UNTRIGGERED);
	return false;

	triggered:
	data = uart_hw_read(); // Clear the RX FIFO
	int write_prep_res = i2c_write_timeout_us(I2C_PMBUS, PMBUS_PMIC_ADDRESS, glitch.cmd_prep, TPS_WRITE_REG_CMD_LEN, false, 100);
	busy_wait_us_32(glitch.ext_offset);
	int write_glitch_res = i2c_write_timeout_us(I2C_PMBUS, PMBUS_PMIC_ADDRESS, glitch.cmd_glitch, TPS_WRITE_REG_CMD_LEN, false, 100);
	busy_wait_us_32(glitch.width);
	int write_restore_res = i2c_write_timeout_us(I2C_PMBUS, PMBUS_PMIC_ADDRESS, glitch.cmd_restore, TPS_WRITE_REG_CMD_LEN, false, 100);

	if (write_prep_res != TPS_WRITE_REG_CMD_LEN | write_glitch_res != TPS_WRITE_REG_CMD_LEN || write_restore_res != TPS_WRITE_REG_CMD_LEN) {
		putchar(P_CMD_RESULT_PMIC_FAIL);
		return false;
	}

	// Check if target is still alive
	t = time_us_32();
	do {
		if (uart_hw_readable()) goto alive;
	} while ((time_us_32() - t) <= TARGET_REACHABLE_US);
	putchar(P_CMD_RESULT_DEAD);
	return false;

	alive:
	data = uart_hw_read();
	switch (data) {
	case T_CMD_NORMAL:
		putchar(P_CMD_RESULT_NORMAL);
		break;
	case T_CMD_SUCCESS:
		readu32_t performed, result_a, result_b;
		uart_hw_readu32(&performed);
		uart_hw_readu32(&result_a);
		uart_hw_readu32(&result_b);
		if (!performed.valid || !result_a.valid || !result_b.valid) {
			putchar(P_CMD_RESULT_DATA_TIMEOUT);
		} else {
			putchar(P_CMD_RESULT_SUCCESS);
			putu32(performed.val);
			putu32(result_a.val);
			putu32(result_b.val);
		}
		break;
	case T_CMD_READY:
		putchar(P_CMD_RESULT_RESET);
		break;
	default:
		putchar(P_CMD_RESULT_ZOMBIE);
		break;
	}
	return true;
}

static void sort(uint32_t *arr, int n) {
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

int estimate_offset(void) {
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
	uint32_t t;
	volatile uint8_t data; // Used to flush the RX FIFO
	uint32_t measurements[ESTIMATE_ROUNDS];
	uint32_t standard_median = 0, extra_delay_median = 0, loop_duration = 0;

	while(uart_hw_readable()) { // Drain buffer
		data = uart_hw_read();
	}

	// Calculate median time between two resets in standard conditions
	for (int i = 0; i < ESTIMATE_ROUNDS; i++) {
		// Wait for connection init from target
		t = time_us_32();
		do {
			if (uart_hw_readable()) goto reachable;
		} while ((time_us_32() - t) <= TARGET_REACHABLE_US);
		return -1;

		reachable:
		uint32_t t1 = time_us_32();
		data = uart_hw_read();
		// Don't send anything, now the target will wait for timeout and then reset

		t = time_us_32();
		do {
			if (uart_hw_readable()) goto reachable2;
		} while ((time_us_32() - t) <= TARGET_REACHABLE_US);
		return -1;

		reachable2:
		uint32_t t2 = time_us_32();
		data = uart_hw_read();

		measurements[i] = t2 - t1;
	}
	sort(measurements, ESTIMATE_ROUNDS);
	standard_median = measurements[ESTIMATE_ROUNDS / 2];

	// Now we will measure the time between two resets when the target adds a fixed delay
	// (same as the one used in the glitching routine) between two resets.
	while(uart_hw_readable()) { // Drain buffer
		data = uart_hw_read();
	}

	// Wait for connection init from target, we need to instruct the target to skip the loop
	t = time_us_32();
	do {
		if (uart_hw_readable()) goto send_cmd;
	} while ((time_us_32() - t) <= TARGET_REACHABLE_US);
	return -1;

	send_cmd:
	data = uart_hw_read();
	uart_hw_write(T_CMD_EXTRA_WAIT); // Tell the target to skip the loop on next reset

	for (int i = 0; i < ESTIMATE_ROUNDS; i++) {
		// Wait for connection init from target
		t = time_us_32();
		do {
			if (uart_hw_readable()) goto reachable3;
		} while ((time_us_32() - t) <= TARGET_REACHABLE_US);
		return -1;

		reachable3:
		uint32_t t1 = time_us_32();
		data = uart_hw_read();
		// Don't send anything, now the target will wait for timeout + extra delay, and then reset

		t = time_us_32();
		do {
			if (uart_hw_readable()) goto reachable4;
		} while ((time_us_32() - t) <= TARGET_REACHABLE_US);
		return -1;

		reachable4:
		uint32_t t2 = time_us_32();
		data = uart_hw_read();
		uart_hw_write(T_CMD_EXTRA_WAIT); // Tell the target to skip the loop on next reset

		measurements[i] = t2 - t1;
	}
	sort(measurements, ESTIMATE_ROUNDS);
	extra_delay_median = measurements[ESTIMATE_ROUNDS / 2];

	if (standard_median >= extra_delay_median) {
		return -2;
	}

	loop_duration = extra_delay_median - standard_median;

	if (loop_duration < PICO_RX_TIME)
		return -3;

	return loop_duration - PICO_RX_TIME;
}

bool __no_inline_not_in_flash_func(uart_debug_pin_toggle)(void) {
	/*
	 * This function can be used to measure (externally) the time between the data
	 * being on the UART channel, and it being available to the Pico.
	 */
	volatile uint8_t data = uart_hw_read(); // Start off with a clean RX data register
	uint32_t t = time_us_32();
	do {
		if (uart_hw_readable()) goto toggle;
	} while ((time_us_32() - t) <= TARGET_REACHABLE_US);
	return false;

	toggle:
	gpio_xor_mask(PIN_DEBUG_MASK);
	return true;
}

uint volt_dot_count = 0;
bool volt_dot_detected = false;
bool volt_done_alive = false;
void irq_voltage_test_counter(void) {
	/* Registered as a UART IRQ, whenever a byte is received it increments volt_dot_count */
	volatile uint8_t d = uart_get_hw(UART_TARGET)->dr; // Clear the interrupt
	if (d == T_CMD_VOLT_TEST_PING) {
		volt_dot_count++;
		volt_dot_detected = true;
	} else if (d == T_CMD_READY && volt_dot_detected) {
		volt_done_alive = true;
	}
}

int voltage_test(void) {
	/*
	 * Test target behavior at a given voltage when sending a fixed number (see target firmware)
	 * of T_CMD_VOLT_TEST_PING characters. The number of actually received characters is returned.
	 * The target voltage must be set before calling this function (P_CMD_SET_VOLTAGE).
	 * This function will count incoming characters before the timeout is reached.
	 *
	 * The drop width and external offset are configured the same way as for the glitching routine.
	 *
	 * Returns:
	 *  - -1: target is unreachable
	 *  - -2: target died during the test
	 *  - -3: could not send command to PMIC to set glitch target voltage/restore standard voltage
	 *  - >=0: the number of received T_CMD_VOLT_TEST_PING characters
	 */

	int ret = 0;
	uint32_t t;
	uint32_t extra_delay = 0;
	volt_dot_count = 0;
	volt_dot_detected = false;
	volt_done_alive = false;

	if (glitch.width > VOLT_TEST_TIMEOUT_US) {
		extra_delay = 0;
	} else {
		extra_delay = VOLT_TEST_TIMEOUT_US - glitch.width;
	}

	irq_set_exclusive_handler(UART0_IRQ, irq_voltage_test_counter);

	volatile uint8_t data = uart_hw_read(); // Start off with a clean RX data register
	t = time_us_32();
	do {
		if (uart_hw_readable()) goto reachable;
	} while ((time_us_32() - t) <= TARGET_REACHABLE_US);
	ret = -1;
	goto end;

	reachable:
	uart_hw_write(T_CMD_VOLT_TEST);

	irq_set_enabled(UART0_IRQ, true);
	uart_set_irq_enables(UART_TARGET, true, false);

	busy_wait_us_32(glitch.ext_offset);
	int write_glitch_res = i2c_write_timeout_us(I2C_PMBUS, PMBUS_PMIC_ADDRESS, glitch.cmd_glitch, TPS_WRITE_REG_CMD_LEN, false, 100);
	busy_wait_us_32(glitch.width);
	int write_restore_res = i2c_write_timeout_us(I2C_PMBUS, PMBUS_PMIC_ADDRESS, glitch.cmd_restore, TPS_WRITE_REG_CMD_LEN, false, 100);
	busy_wait_us_32(extra_delay); // Wait for the target to send all the data back

	uart_set_irq_enables(UART_TARGET, false, false);
	irq_set_enabled(UART0_IRQ, false);

	if (write_glitch_res != TPS_WRITE_REG_CMD_LEN || write_restore_res != TPS_WRITE_REG_CMD_LEN) {
		ret = -3;
	} else if (!volt_done_alive) {
		ret = -2;
	} else {
		ret = volt_dot_count;
	}

	end:
	return ret;
}
