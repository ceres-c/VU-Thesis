#ifndef TARGET_UART_H
#define TARGET_UART_H

#include "picocoder.h"

void target_uart_init(void);
void on_uart_rx(void);

inline void uart_enable(void) {
	*SET_GPIO_ATOMIC = 1 << PIN_UART_OE;
}
inline void uart_disable(void) {
	*CLR_GPIO_ATOMIC = 1 << PIN_UART_OE;
}

#endif // TARGET_UART_H
