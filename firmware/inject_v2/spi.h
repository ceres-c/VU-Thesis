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

#ifndef _SPI_H
#define _SPI_H

#include <stdint.h>
#include "pico/stdlib.h"
#include "pio/pio_spi.h"
#include "picocoder.h"

uint32_t serprog_spi_init(pio_spi_inst_t *spi, uint32_t freq);

static inline void cs_select(uint cs_pin) {
	asm volatile("nop \n nop \n nop"); // FIXME
	gpio_put(cs_pin, 0);
	asm volatile("nop \n nop \n nop"); // FIXME
}

static inline void cs_deselect(uint cs_pin) {
	asm volatile("nop \n nop \n nop"); // FIXME
	gpio_put(cs_pin, 1);
	asm volatile("nop \n nop \n nop"); // FIXME
}

#endif // _SPI_H
