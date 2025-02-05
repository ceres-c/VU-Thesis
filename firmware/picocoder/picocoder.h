#ifndef _PICOCODER_H
#define _PICOCODER_H

#include <stdio.h>
#include <string.h>
#include "pico/binary_info.h"
#include "pico/stdlib.h"
#include "pio/pio_spi.h"
#include "hardware/clocks.h"
#include "hardware/i2c.h"

// Registers for SIO
#define GPIO_ATOMIC				((volatile uint32_t*)(SIO_BASE + SIO_GPIO_OUT_OFFSET))
#define SET_GPIO_ATOMIC			((volatile uint32_t*)(SIO_BASE + SIO_GPIO_OUT_SET_OFFSET))
#define CLR_GPIO_ATOMIC			((volatile uint32_t*)(SIO_BASE + SIO_GPIO_OUT_CLR_OFFSET))
#define XOR_GPIO_ATOMIC			((volatile uint32_t*)(SIO_BASE + SIO_GPIO_OUT_XOR_OFFSET))

#define SPI_PIO					pio1
#define UART_TARGET				uart0
#define I2C_PMBUS				i2c0
#define PMBUS_BAUD				1000000 // 1 MHz
#define UART_TARGET_PTR			((uart_hw_t *)UART_TARGET)
#define UART_TARGET_BAUD		115200
#define UART_TARGET_DATA_BITS	8
#define UART_TARGET_STOP_BITS	1
#define UART_TARGET_PARITY		UART_PARITY_NONE

#define PIN_LED PICO_DEFAULT_LED_PIN
#define PIN_UART_TX		0	// Pin 1
#define PIN_UART_RX		1	// Pin 2
#define PIN_UART_OE		2	// Pin 4 - Level shifter output Enable
#define PIN_PMBUS_SDA	8	// Pin 11 (Can't use 4 and 5 because of funny soldering on my board)
#define PIN_PMBUS_SCL	9	// Pin 12
#define PIN_SPI_MISO	28	// Pin 34
#define PIN_SPI_MOSI	27	// Pin 32
#define PIN_SPI_SCK		26	// Pin 31
#define PIN_SPI_CS		22	// Pin 29
#define PIN_DEBUG		3	// Pin 5
#define PIN_DEBUG_MASK	(1 << PIN_DEBUG)
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

uint32_t getu24();
uint32_t getu32();
void putu32(uint32_t d);

#endif // _PICOCODER_H
