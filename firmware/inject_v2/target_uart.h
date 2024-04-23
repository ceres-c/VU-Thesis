#ifndef TARGET_UART_H
#define TARGET_UART_H

#include "picocoder.h"
#include "cmd.h"

void target_uart_init(void);

inline void uart_shifter_enable(void) {
	*SET_GPIO_ATOMIC = 1 << PIN_UART_OE;
}
inline void uart_shifter_disable(void) {
	*CLR_GPIO_ATOMIC = 1 << PIN_UART_OE;
}
inline void uart_enable_irq(void) {
	uart_set_irq_enables(UART_TARGET, true, false);
}
inline void uart_disable_irq(void) {
	uart_set_irq_enables(UART_TARGET, false, false);
}

#endif // TARGET_UART_H
