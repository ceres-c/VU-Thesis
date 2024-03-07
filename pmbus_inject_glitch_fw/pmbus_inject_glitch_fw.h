#ifndef _PMBUS_INJECT_GLITCH_FW_H
#define _PMBUS_INJECT_GLITCH_FW_H

#include <stdio.h>
#include <stdlib.h> // strtoul

#include "pico/stdlib.h"
#include "pico/stdio_usb.h"
#include "pico/i2c_slave.h"
#include "pico/multicore.h"
#include "hardware/structs/xip_ctrl.h" // To disable cache
#include "hardware/i2c.h"

#define PMBUS_MASTER_OE_PIN			3 // Pin 5
#define PMBUS_MASTER_OE_MASK		(1 << PMBUS_MASTER_OE_PIN)
#define PMBUS_MASTER_SDA_PIN		4 // Pin 6
#define PMBUS_MASTER_SCL_PIN		5 // Pin 7
#define PMBUS_SLAVE_SDA_PIN			6 // Pin 9
#define PMBUS_SLAVE_SCL_PIN			7 // Pin 10
#define TRIGGER_IN_PIN				8 // Pin 11

#define PMBUS_PMIC_ADDRESS			0x5E // Stated in the datasheet and confirmed sniffing the I2C bus

#define TPS_REG_BUCK1CTRL			0x20
#define TPS_REG_BUCK2CTRL			0x21
#define TPS_REG_BUCK3CTRL			0x23
#define TPS_REG_BUCK4CTRL			0x25
#define TPS_REG_BUCK5CTRL			0x26
#define TPS_REG_BUCK6CTRL			0x27
#define TPS_REG_DISCHCNT1			0x40
#define TPS_REG_DISCHCNT2			0x41
#define TPS_REG_DISCHCNT3			0x42
#define TPS_REG_POK_DELAY			0x43
#define TPS_REG_FORCESHUTDN			0x91
#define TPS_REG_BUCK4VID			0x94
#define TPS_REG_BUCK5VID			0x96
#define TPS_REG_BUCK6VID			0x98
#define TPS_REG_LDOA2VID			0x9A
#define TPS_REG_LDOA3VID			0x9B
#define TPS_REG_VR_CTRL1			0x9C
#define TPS_REG_VR_CTRL2			0x9E
#define TPS_REG_VR_CTRL3			0x9F
#define TPS_REG_GPO_CTRL			0xA1
#define TPS_REG_PWR_FAULT_MASK1		0xA2
#define TPS_REG_PWR_FAULT_MASK2		0xA3
#define TPS_REG_DISCHCNT4			0xAD
#define TPS_REG_LDOA1CTRL			0xAE
#define TPS_REG_PG_STATUS1			0xB0
#define TPS_REG_PG_STATUS2			0xB1
#define TPS_REG_PWR_FAULT_STATUS1	0xB2
#define TPS_REG_PWR_FAULT_STATUS2	0xB3
#define TPS_REG_TEMPHOT				0xB5

#define TPS_WRITE_REG_CMD_LEN		2

#define pmbus_master_i2c			i2c0
#define pmbus_slave_i2c				i2c1

#define TPS_VCORE_ZERO				0b00000000 // 0V
#define TPS_VCORE_MIN				0b00000001 // 0.5V
#define TPS_VCORE_MIN_V				0.5f
#define TPS_VCORE_MAX				0b01010001 // 1.3V - Arbitrary decided to not fry the CPU
#define TPS_VCORE_MAX_V				1.3f

#define CMD_PING					'P'
#define CMD_EXT_OFFSET				'E' // How long to wait before triggering the glitch after a trigger (uint32_t)
#define CMD_SET_GLITCH_WIDTH		'W' // The width of a single glitch pulse (uint32_t)
#define CMD_SET_GLITCH_VOLTAGE		'V' // The voltage to inject (uint8_t)
#define CMD_GET_I2C_VCORE			'v' // Get the current VCORE read from the i2c bus (uint8_t)
#define CMD_TRIGGER_USB				'T' // Force a trigger
#define CMD_ARM						'A' // Arm the glitcher
#define CMD_DISARM					'D' // Disarm the glitcher

#define RESP_OK						'k'
#define RESP_KO						'x'
#define RESP_PONG					'p'
#define RESP_GLITCH_SUCCESS			'!' // The glitch value was sent successfully
#define RESP_GLITCH_FAIL			'.' // The glitch value was not sent successfully

typedef struct i2c_sniff_data_s {
	uint8_t reg_address;
	bool reg_address_written;
	uint8_t value;
} i2c_sniff_data_t;

typedef struct glitch_s {
	uint32_t ext_offset;
	uint32_t width;
	uint8_t reg_value;
} glitch_t;

static void init_pins();
static void __not_in_flash_func(i2c_slave_recv_irq)(i2c_inst_t *i2c, i2c_slave_event_t event);
void glitch_gpio_trig_enable();
void glitch_gpio_trig_disable();
void do_glitch();

inline uint8_t atou8(char *str, char *endptr) {
	/**
	 * @brief Convert a string to an unsigned integer (no error checking).
	 * Parses binary, decimal, or hexadecimal numbers.
	 *
	 * @param str The string to convert
	 * @param endptr Reference to an object of type char*, whose value is
	 * set by the function to the next character in str after the numerical value.
	 * This parameter can also be a null pointer, in which case it is not used.
	 * @return uint8_t The converted value
	 * 
	*/
	if (str[0] == '0' && (str[1] == 'x' || str[1] == 'X')) {
		return (uint8_t)strtoul(str, &endptr, 16);
	} else if (str[0] == '0' && (str[1] == 'b' || str[1] == 'B')) {
		return (uint8_t)strtoul(str, &endptr, 2);
	} else {
		return (uint8_t)strtoul(str, &endptr, 10);
	}
}

inline void getline(char *str, size_t size) {
	/**
	 * @brief Read a line from the standard input
	 *
	 * @param str The buffer to store the line
	 * @param size The size of the buffer
	 * 
	*/
	for (size_t i = 0; i < size; i++) {
		str[i] = getchar();
		if (str[i] == '\n' || str[i] == '\r' || str[i] == '\0' || str[i] == EOF) {
			str[i] = '\0';
			break;
		}
	}
}

#endif // _PMBUS_INJECT_GLITCH_FW_H
