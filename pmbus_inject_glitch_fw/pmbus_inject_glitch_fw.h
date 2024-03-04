#ifndef _PMBUS_INJECT_GLITCH_FW_H
#define _PMBUS_INJECT_GLITCH_FW_H

#include <stdio.h>

#include "pico/stdlib.h"
#include "pico/stdio_usb.h"
#include "hardware/structs/xip_ctrl.h" // To disable cache
#include "hardware/i2c.h"

#define I2C_WRITE					0
#define I2C_READ					1

#define PMBUS_MASTER_OE_PIN			3 // Pin 5
#define PMBUS_MASTER_SDA_PIN		4 // Pin 6
#define PMBUS_MASTER_SCL_PIN		5 // Pin 7

#define TPS_PMBUS_ADDRESS			0x5E // Stated in the datasheet and confirmed sniffing the I2C bus

#define TPS_CMD_BUCK1CTRL			0x20
#define TPS_CMD_BUCK2CTRL			0x21
#define TPS_CMD_BUCK3CTRL			0x23
#define TPS_CMD_BUCK4CTRL			0x25
#define TPS_CMD_BUCK5CTRL			0x26
#define TPS_CMD_BUCK6CTRL			0x27
#define TPS_CMD_DISCHCNT1			0x40
#define TPS_CMD_DISCHCNT2			0x41
#define TPS_CMD_DISCHCNT3			0x42
#define TPS_CMD_POK_DELAY			0x43
#define TPS_CMD_FORCESHUTDN			0x91
#define TPS_CMD_BUCK4VID			0x94
#define TPS_CMD_BUCK5VID			0x96
#define TPS_CMD_BUCK6VID			0x98
#define TPS_CMD_LDOA2VID			0x9A
#define TPS_CMD_LDOA3VID			0x9B
#define TPS_CMD_VR_CTRL1			0x9C
#define TPS_CMD_VR_CTRL2			0x9E
#define TPS_CMD_VR_CTRL3			0x9F
#define TPS_CMD_GPO_CTRL			0xA1
#define TPS_CMD_PWR_FAULT_MASK1		0xA2
#define TPS_CMD_PWR_FAULT_MASK2		0xA3
#define TPS_CMD_DISCHCNT4			0xAD
#define TPS_CMD_LDOA1CTRL			0xAE
#define TPS_CMD_PG_STATUS1			0xB0
#define TPS_CMD_PG_STATUS2			0xB1
#define TPS_CMD_PWR_FAULT_STATUS1	0xB2
#define TPS_CMD_PWR_FAULT_STATUS2	0xB3
#define TPS_CMD_TEMPHOT				0xB5

#define pmbus_i2c					i2c0

#endif // _PMBUS_INJECT_GLITCH_FW_H
