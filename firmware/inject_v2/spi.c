/**
 * All SPI code is written by Thomas Roth - code@stacksmashing.net
 * 
 * Licensed under GPLv3
 * 
 * Based on the spi_flash pico-example, which is:
 *  Copyright (c) 2020 Raspberry Pi (Trading) Ltd.
 * Also based on stm32-vserprog: 
 *  https://github.com/dword1511/stm32-vserprog
 * 
 */

#include "spi.h"

uint32_t serprog_spi_init(pio_spi_inst_t *spi, uint32_t freq) {
	// Initialize CS
	gpio_init(PIN_SPI_CS);
	gpio_put(PIN_SPI_CS, 1);
	gpio_set_dir(PIN_SPI_CS, GPIO_OUT);

	uint spi_offset = pio_add_program(spi->pio, &spi_cpha0_program);

	float clkdiv = freq_to_clkdiv(freq);

	pio_spi_init(spi->pio, spi->sm, spi_offset,
				 8,			// 8 bits per SPI frame
				 clkdiv,
				 false,		// CPHA = 0
				 false,		// CPOL = 0
				 PIN_SPI_SCK,
				 PIN_SPI_MOSI,
				 PIN_SPI_MISO);

	return clkdiv_to_freq(clkdiv);
}