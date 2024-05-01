#include "glitch.h"

target_state_t target_state = TARGET_IGNORE;
uint8_t pmbus_cmd_glitch[TPS_WRITE_REG_CMD_LEN] = {TPS_REG_BUCK2CTRL, TPS_VCORE_MIN};
uint8_t pmbus_cmd_restore[TPS_WRITE_REG_CMD_LEN] = {TPS_REG_BUCK2CTRL, TPS_VCORE_SAFE};
uint8_t retval[4] = {0, 0, 0, 0};
uint8_t ret_i = 0;

inline static void uart_hw_write(uint8_t data) {
	UART_TARGET_PTR->dr = data;
}
inline static uint8_t uart_hw_read(void) {
	return UART_TARGET_PTR->dr;
}
inline static bool uart_hw_readable(void) {
	return !(UART_TARGET_PTR->fr & UART_UARTFR_RXFE_BITS);
}
inline static uint8_t uart_hw_read_blocking(void) {
	while (!uart_hw_readable())
		tight_loop_contents();
	return uart_hw_read();
}
inline static uint8_t uart_hw_read_timeout_cycles(uint32_t timeout_cycles) {
	for (uint32_t i = 0; i < timeout_cycles; i++) {
		if (uart_hw_readable())
			return uart_hw_read();
	}
	return STDIO_NO_INPUT;
}
static uint32_t uart_getu32_timeout_cycles(uint32_t timeout_cycles) {
	bool irq_state = irq_is_enabled(UART_TARGET_IRQ);
	irq_set_enabled(UART_TARGET_IRQ, false);
	uint32_t c1 = uart_hw_read_timeout_cycles(timeout_cycles);
	uint32_t c2 = uart_hw_read_timeout_cycles(timeout_cycles);
	uint32_t c3 = uart_hw_read_timeout_cycles(timeout_cycles);
	uint32_t c4 = uart_hw_read_timeout_cycles(timeout_cycles);
	irq_set_enabled(UART_TARGET_IRQ, irq_state);
	if (c1 == STDIO_NO_INPUT || c2 == STDIO_NO_INPUT || c3 == STDIO_NO_INPUT || c4 == STDIO_NO_INPUT)
		return STDIO_NO_INPUT;
	return c1 | (c2<<8) | (c3<<16) | (c4<<24);
}

static void irq_uart_glitch(void);

void target_uart_init(void) {
	uart_init(UART_TARGET, UART_TARGET_BAUD);

	gpio_set_function(PIN_UART_TX, GPIO_FUNC_UART);
	gpio_set_function(PIN_UART_RX, GPIO_FUNC_UART);
	gpio_set_function(PIN_UART_OE, GPIO_FUNC_SIO);
	gpio_set_dir(PIN_UART_OE, GPIO_OUT);

	uart_set_hw_flow(UART_TARGET, false, false);
	uart_set_format(UART_TARGET, UART_TARGET_DATA_BITS, UART_TARGET_STOP_BITS, UART_TARGET_PARITY);
	uart_set_fifo_enabled(UART_TARGET, false); // Char by char

	// RX interrupt
	target_state = TARGET_IGNORE;
	if (uart_is_readable_within_us(UART_TARGET, 100)) // Drain buffer
		uart_getc(UART_TARGET);
	irq_set_exclusive_handler(UART_TARGET_IRQ, irq_uart_glitch);
	irq_set_enabled(UART_TARGET_IRQ, true);
}

void uart_echo(void) {
	puts("UART echo, power cycle to exit");
	uart_level_shifter_enable();
	while (true) {
		char c = getchar_timeout_us(0);
		if (c != PICO_ERROR_TIMEOUT) {
			uart_hw_write(c);
		}
		if (uart_hw_readable()) {
			putchar(uart_hw_read_blocking());
		}
	}
}

static void irq_uart_glitch(void) {
	uint8_t data = uart_hw_read_blocking();

	switch (target_state) {
	case TARGET_UNKNOWN:
		if (data == T_CMD_RESET) {			// Target is starting over
			target_state = TARGET_READY;
			uart_hw_write(T_CMD_CONNECT);	// ACK connection
		} else {							// Sometimes we get garbage when the board boots
			target_state = TARGET_UNKNOWN;
			uart_hw_write(T_CMD_BOGUS1);	// Random byte to reset the target
		}
		break;
	case TARGET_READY:
		if (data == T_CMD_TRIGGER) {		// Target is telling us to glitch
			target_state = TARGET_GLITCHED;
			// busy_wait_us_32(glitch.ext_offset); // TODO decomment
			int write_glitch_res = i2c_write_timeout_us(I2C_PMBUS, PMBUS_PMIC_ADDRESS, pmbus_cmd_glitch, TPS_WRITE_REG_CMD_LEN, false, 100);
			// busy_wait_us_32(glitch.width); // TODO decomment
			// busy_wait_us_32(1000);
			int write_restore_res = i2c_write_timeout_us(I2C_PMBUS, PMBUS_PMIC_ADDRESS, pmbus_cmd_restore, TPS_WRITE_REG_CMD_LEN, false, 100);
		} else {
			target_state = TARGET_UNKNOWN;	// Go back to base state
			uart_hw_write(T_CMD_BOGUS2);	// Random byte to reset the target
		}
		break;
	case TARGET_GLITCHED:
		target_state = TARGET_IGNORE;
		if (data == T_CMD_RESET) {			// Target died
			putchar(P_CMD_RESULT_RESET);
			uart_hw_write(T_CMD_CONNECT);	// Send connection ack
		} else if (data == T_CMD_ALIVE) {	// Target is still alive!
			uint32_t response = uart_getu32_timeout_cycles(READ_TIMEOUT_CYCLES); // At 115200 baud, each byte 8N1 takes 78us. Well within this timeout
			// uint32_t response = uart_getu32();
			if (response == STDIO_NO_INPUT) {
				putchar(P_CMD_RESULT_DATA_TIMEOUT);
			} else {
				putchar(P_CMD_RESULT_ALIVE);
				putu32(response);
			}
		} else {							// Huh?
			putchar(P_CMD_RESULT_WEIRD);
			uart_hw_write(T_CMD_BOGUS3);	// Random byte to reset the target
		}
		break;
	case TARGET_IGNORE:
	default:
		break;
	}

	return;
}
