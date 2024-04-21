#include "target_uart.h"

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
	while (uart_is_readable(UART_TARGET)) {
		putchar(uart_getc(UART_TARGET));
	}
}
