#include "target_uart.h"

#define UART_HW_UARTDR_DATA_MASK 0xFF

inline static void uart_hw_write(uint8_t data) {
	UART_TARGET_PTR->dr = data;
}
inline static uint8_t uart_hw_read(void) {
	return UART_TARGET_PTR->dr & UART_HW_UARTDR_DATA_MASK; // TODO remove & if not needed
}
inline static bool uart_hw_readable(void) {
	return UART_TARGET_PTR->fr & UART_UARTFR_RXFE_BITS;
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
	TARGET_READY,
} target_state_t;
static target_state_t target_state = TARGET_READY;

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
	irq_set_exclusive_handler(UART_IRQ, on_uart_rx);
	irq_set_enabled(UART_IRQ, true);
	uart_set_irq_enables(UART_TARGET, true, false);
}

void on_uart_rx(void) {
	uint8_t data = uart_hw_read();
	printf("on_uart_rx: State: %d, data: %c\n", target_state, data); // TODO remove

	switch (target_state) {
	case TARGET_UNKNOWN:
		if (data == 'R') {				// Target is starting over
			target_state = TARGET_READY;
			uart_hw_write('C');			// Send connection ack
		} else if (data == 'A') {		// Target is still alive
			uint32_t response = uart_getu32();
			// putchar(P_CMD_RESULT_ALIVE); // TODO decomment
			putu32(response);
		} else {
			target_state = TARGET_UNKNOWN;
			uart_hw_write('X');			// Random byte to reset the target
		}
		break;
	case TARGET_READY:
		if (data == 'T') {				// Target is telling us to glitch
			// TODO do glitch here
			// 1) wait for ext_offset
			// 2) drop voltage
			// 3) wait for width
			// 4) restore voltage
			// 5) Wait for 'A' from target or timeout
		} else {
			uart_hw_write('X');			// Random byte to reset the target
		}
		target_state = TARGET_UNKNOWN;	// Go back to base state
		break;
	}

	return;

	// while (uart_is_readable_within_us(UART_TARGET, 0)) { // At 115200 baud, 1 bit is 8.68us
	// 	// Drain the buffer
	// 	uart_getc(UART_TARGET);
	// }
}
