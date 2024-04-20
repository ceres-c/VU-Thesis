#ifndef _PICOCODER_H
#define _PICOCODER_H

#include <stdio.h>
#include <string.h>
#include "pico/binary_info.h"
#include "pico/stdlib.h"
#include "pio/pio_spi.h"
#include "hardware/clocks.h"
#include "cmd.h"
#include "spi.h"
#include "target_uart.h"

#define SPI_PIO		pio1

#define PIN_LED PICO_DEFAULT_LED_PIN
#define PIN_UART_TX		0	// Pin 1
#define PIN_UART_RX		1	// Pin 2
#define PIN_SPI_MISO	28	// Pin 34
#define PIN_SPI_MOSI	27	// Pin 32
#define PIN_SPI_SCK		26	// Pin 31
#define PIN_SPI_CS		22	// Pin 29
#define BUS_SPI			(1 << 3)
#define S_SUPPORTED_BUS	BUS_SPI
#define S_CMD_MAP ( \
	(1 << S_CMD_NOP)		| \
	(1 << S_CMD_Q_IFACE)	| \
	(1 << S_CMD_Q_CMDMAP)	| \
	(1 << S_CMD_Q_PGMNAME)	| \
	(1 << S_CMD_Q_SERBUF)	| \
	(1 << S_CMD_Q_BUSTYPE)	| \
	(1 << S_CMD_SYNCNOP)	| \
	(1 << S_CMD_O_SPIOP)	| \
	(1 << S_CMD_S_BUSTYPE)	| \
	(1 << S_CMD_S_SPI_FREQ)	| \
	(1 << S_CMD_S_PIN_STATE) \
)

static inline float freq_to_clkdiv(uint32_t freq) {
	float div = clock_get_hz(clk_sys) * 1.0 / (freq * pio_spi_cycles_per_bit);

	if (div < 1.0)
		div = 1.0;
	if (div > 65536.0)
		div = 65536.0;

	return div;
}

static inline uint32_t clkdiv_to_freq(float div) {
	return clock_get_hz(clk_sys) / (div * pio_spi_cycles_per_bit);
}

#endif // _PICOCODER_H
