#include "target_uart.h"

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

static uint32_t uart_getu32() {
	uint32_t c1 = uart_getc(UART_TARGET);
	uint32_t c2 = uart_getc(UART_TARGET);
	uint32_t c3 = uart_getc(UART_TARGET);
	uint32_t c4 = uart_getc(UART_TARGET);
	return c1 | (c2<<8) | (c3<<16) | (c4<<24);
}

typedef enum {
	TARGET_UNKNOWN,
	TARGET_GLITCHED,
	TARGET_READY,
} target_state_t;
static target_state_t target_state = TARGET_UNKNOWN;

void target_uart_init(void) {
	putchar('U');
	uart_init(UART_TARGET, UART_TARGET_BAUD);

	gpio_set_function(PIN_UART_TX, GPIO_FUNC_UART);
	gpio_set_function(PIN_UART_RX, GPIO_FUNC_UART);
	gpio_set_function(PIN_UART_OE, GPIO_FUNC_SIO);
	gpio_set_pulls(PIN_UART_RX, false, true);
	gpio_set_dir(PIN_UART_OE, GPIO_OUT);

	uart_set_hw_flow(UART_TARGET, false, false);
	uart_set_format(UART_TARGET, UART_TARGET_DATA_BITS, UART_TARGET_STOP_BITS, UART_TARGET_PARITY);
	uart_set_fifo_enabled(UART_TARGET, false); // Char by char

	// RX interrupt
	int UART_IRQ = UART_TARGET == uart0 ? UART0_IRQ : UART1_IRQ;
	if (uart_is_readable_within_us(UART_TARGET, 100)) // Drain buffer
		uart_getc(UART_TARGET);
	irq_set_exclusive_handler(UART_IRQ, on_uart_rx);
	irq_set_enabled(UART_IRQ, true);
	uart_set_irq_enables(UART_TARGET, true, false);
}

static void on_uart_rx(void) {
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
			// TODO do glitch here
			// 1) wait for ext_offset
			// 2) drop voltage
			// 3) wait for width
			// 4) restore voltage
			// 5) Wait for 'A' from target or timeout
		} else {
			target_state = TARGET_UNKNOWN;	// Go back to base state
			uart_hw_write(T_CMD_BOGUS2);	// Random byte to reset the target
		}
		break;
	case TARGET_GLITCHED:
		if (data == T_CMD_RESET) {			// Target died
			target_state = TARGET_READY;
			putchar(P_CMD_RESULT_RESET);
			uart_hw_write(T_CMD_CONNECT);	// Send connection ack
		} else if (data == T_CMD_ALIVE) {	// Target is still alive!
			target_state = TARGET_UNKNOWN;
			uint32_t response = uart_getu32();
			putchar(P_CMD_RESULT_ALIVE);
			putu32(response);
		} else {							// Huh?
			target_state = TARGET_UNKNOWN;
			putchar(P_CMD_RESULT_WEIRD);
			uart_hw_write(T_CMD_BOGUS3);	// Random byte to reset the target
		}
		break;
	}

	return;
}
